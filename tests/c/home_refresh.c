/* An ungranted/nested invocation must not consume another frame's token. */
#include <assert.h>
#include "refresh_policy.h"

int main(void)
{
    HomeRefreshState refresh = {0};
    unsigned token = home_refresh_begin(&refresh);
    assert(token && home_refresh_begin(&refresh) == 0);
    assert(home_refresh_finish(&refresh, 0) == 0 && refresh.busy == token);
    assert(home_refresh_finish(&refresh, token + 1) == -1 && refresh.busy == token);
    assert(home_refresh_finish(&refresh, token) == 1 && !refresh.busy);
    assert(home_refresh_finish(&refresh, token) == -1);
    refresh.serial = 0xffffffffu;
    assert(home_refresh_begin(&refresh) == 1);
    assert(home_refresh_finish(&refresh, 1) == 1);
    return 0;
}
