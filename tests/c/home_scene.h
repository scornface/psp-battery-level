/* Measured normal-scene inputs shared by session tests, not expected outputs. */
#ifndef TEST_HOME_SCENE_H
#define TEST_HOME_SCENE_H
#include "binding_policy.h"

static HomeBinding test_home_binding(void)
{
    return (HomeBinding){42, 0x8a100000u, 0xaa100000u};
}

static HomeNativeState test_home_scene(void)
{
    return (HomeNativeState){
        42, 0x8a100000u, 0xaa100000u, 512, 272, 0x50102, 0x3bf, 338, 1, 1, 0, 0, 2, 0, 0x6800
    };
}
#endif
