/* Synthetic acquisition providers verify ordering and transactional failure,
 * not SHA-1 itself or Sony asset appearance (checked separately offline). */
#include <assert.h>
#include <string.h>
#include "assets.h"
#include "pgf.h"
enum { OPEN=1, READ, CLOSE, SHORT, LONG, HASH_ERROR, HASH_MISMATCH, BAD_OFFSET,
       BAD_LENGTH, DECODE, BAD_GLYPH, SPRITE_HASH_ERROR, SPRITE_HASH_MISMATCH, OVERSIZED_READ };
static HomeAssetWorkspace work;
static HomeAssets result, saved;
static unsigned char resource[113677], font[41001];
static int failure, target, active, opens, closes, hashes, decoded;
static unsigned position;
static const unsigned char expected[3][20]={
 {0x3f,0x91,0xe6,0xc8,0xf5,0xeb,0x14,0xcd,0x31,0x80,0x23,0x5b,0xaa,0x39,0x65,0x93,0xc4,0x95,0x97,0x0f},
 {0xca,0xf7,0x1c,0x8b,0xed,0x92,0x37,0x49,0xea,0x3b,0x8b,0xb9,0x6b,0xc0,0xa5,0x8c,0x4c,0x10,0x52,0x98},
 {0x1a,0x01,0x1d,0xc6,0x1c,0xb7,0x72,0x18,0xf5,0x48,0xdc,0xf6,0x24,0xbb,0x18,0x79,0x04,0xdd,0x82,0x94}};
static void put32(unsigned at,unsigned value) {
    for(unsigned i=0;i<4;++i)resource[at+i]=(unsigned char)(value>>(8*i));
}
static void init(void) {
    active=opens=closes=hashes=decoded=0;position=0;target=1;
    memset(resource,0,sizeof(resource));memset(font,0,sizeof(font));
    put32(112,256);put32(256,4800);
    for(unsigned d=0;d<10;++d)for(unsigned i=0;i<240;++i) {
        unsigned value=i%16<(d==1?6u:10u)?0xffff:0x9ce7;
        unsigned at=260+(d*240+i)*2;resource[at]=(unsigned char)value;resource[at+1]=(unsigned char)(value>>8);
    }
    memset(&result,0xa5,sizeof(result));saved=result;
}
int sceIoOpen(const char *path,int flags,int mode) {
    assert(!active && flags==1 && mode==0);++opens;
    assert(!strcmp(path,opens==1?"flash0:/kd/resource/impose.rsc":"flash0:/font/ltn8.pgf"));
    if(opens==2)assert(hashes==1 && !decoded);
    if(failure==OPEN && target==opens)return -1;
    active=opens;position=0;return active;
}
int sceIoRead(int fd,void *buffer,unsigned count) {
    assert(active==fd && count>0);
    if(target==active && failure==READ)return -1;
    if(target==active && failure==OVERSIZED_READ)return (int)count+1;
    unsigned length=active==1?113676u:41000u;
    if(target==active && failure==SHORT)--length;
    if(target==active && failure==LONG)++length;
    if(position==length)return 0;
    if(count>97)count=97; /* Force hundreds of partial reads. */
    if(count>length-position)count=length-position;
    memcpy(buffer,(active==1?resource:font)+position,count);position+=count;
    return (int)count;
}
int sceIoClose(int fd) {
    assert(active==fd);active=0;++closes;
    return failure==CLOSE && fd==target?-1:0;
}
int sceKernelUtilsSha1Digest(unsigned char *bytes,unsigned size,unsigned char *digest) {
    assert(!active);int index=hashes++;
    assert(index<3 && size==(index==0?113676u:index==1?41000u:1920u));
    if((failure==HASH_ERROR && target==index+1) || (failure==SPRITE_HASH_ERROR && index==2))return -1;
    memcpy(digest,expected[index],20);
    if((failure==HASH_MISMATCH && target==index+1) || (failure==SPRITE_HASH_MISMATCH && index==2))digest[0]^=1;
    if(index==0)assert(!memcmp(bytes,resource,size));
    if(index==1)assert(!memcmp(bytes,font,size));
    return 0;
}
int pgf_glyph(const unsigned char *data,size_t size,unsigned character,PgfGlyph *out) {
    assert(!active && hashes==2 && size==41000 && character=='%' && !memcmp(data,font,size));
    ++decoded;
    if(failure==DECODE)return -1;
    memset(out,0,sizeof(*out));out->width=failure==BAD_GLYPH?12:11;out->height=11;
    for(unsigned i=0;i<11;++i)out->pixels[i*11+i]=15;
    return 0;
}
static void test_preparation_owns_all_output(void) {
    init();failure=0;assert(home_assets_prepare(&result,&work)==0);
    assert(opens==2 && closes==2 && hashes==3 && decoded==1 && !active);
    assert(result.tiles.ready && result.reference.percent==100 && result.reference.height==15);
    assert(!memcmp(result.tiles.pixels,work.atlas,sizeof(work.atlas)));
    /* Output cannot retain a pointer into reclaimed scratch. */
    saved=result;memset(&work,0,sizeof(work));
    assert(!memcmp(&saved,&result,sizeof(result)));
}

static void test_failures_are_transactional(void) {
    for(int f=OPEN;f<=OVERSIZED_READ;++f) {
      /* Only per-file I/O and authentication failures need both targets. */
      int targets=f<=HASH_MISMATCH || f==OVERSIZED_READ?2:1;
      for(int t=1;t<=targets;++t) {
        init();failure=f;target=t;
        if(f==BAD_OFFSET)put32(112,113676-4803);
        if(f==BAD_LENGTH)put32(256,4799);
        int code=home_assets_prepare(&result,&work);
        int expected_code=f<=LONG || f==OVERSIZED_READ?-10:
                          f==DECODE?-13:f>=BAD_GLYPH && f<=SPRITE_HASH_MISMATCH?-14:-11;
        assert(code==expected_code && !active);
        assert(closes==opens-(f==OPEN?1:0));
        assert(!memcmp(&saved,&result,sizeof(result)));
        if(f<=HASH_MISMATCH || f==OVERSIZED_READ)assert(decoded==0);
      }
    }
}

static void test_invalid_storage_precedes_io(void) {
    init();failure=0;
    assert(home_assets_prepare(0,&work)==-1);
    assert(home_assets_prepare(&result,0)==-1);
    assert(home_assets_prepare(&work.prepared,&work)==-1);
    assert(home_assets_prepare((HomeAssets *)&work,&work)==-1);
    assert(!opens && !memcmp(&saved,&result,sizeof(result)));
}

int main(void) {
    test_preparation_owns_all_output();
    test_failures_are_transactional();
    test_invalid_storage_precedes_io();
    return 0;
}
