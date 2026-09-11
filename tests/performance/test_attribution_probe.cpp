// SPDX-License-Identifier: MIT
// Valid lifecycle and deliberately broken diagnostic accounting contracts.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <limits>
#include <new>
#include "attribution_probe.h"

int main(int argc,char **argv)
{
    if(argc!=2)return 2;
    std::ios::sync_with_stdio(false);std::cerr.unsetf(std::ios::unitbuf);std::cerr.tie(nullptr);
    allocation_probe::reset();
    attribution_probe::begin_trial("contract","lifetime",1,0,0);
    attribution_probe::begin_frame(-1,"warmup");
    if(std::strcmp(argv[1],"histogram_overflow")==0)
    {
        allocation_probe::enabled=true;
        attribution_probe::Scope scope(attribution_probe::Phase::synchronization,1);
        for(size_t size=1;size<=65;++size){void *value=::operator new(size);::operator delete(value);}
        return 3;
    }
    const size_t site=std::strcmp(argv[1],"unattributed")==0?0:1;
    void *value=nullptr;
    allocation_probe::enabled=true;
    {attribution_probe::Scope scope(attribution_probe::Phase::synchronization,site);value=::operator new(24);}
    allocation_probe::enabled=false;
    if(std::strcmp(argv[1],"surviving_allocation")==0){allocation_probe::reset();return 3;}
    attribution_probe::emit_frame(1,24,24);
    attribution_probe::begin_frame(0);
    allocation_probe::enabled=true;
    {attribution_probe::Scope scope(attribution_probe::Phase::returned_destruction,4);::operator delete(value);}
    allocation_probe::enabled=false;
    if(std::strcmp(argv[1],"reconcile_failure")==0){attribution_probe::emit_frame(1,0,0);return 3;}
    attribution_probe::emit_frame(0,0,0);
    const auto &birth=attribution_probe::sites[1];
    if(birth.frees!=1||birth.lifetime_frames_max!=1||birth.same_frame_frees!=0||
        birth.free_phase_counts[size_t(attribution_probe::Phase::returned_destruction)]!=1)return 5;
    allocation_probe::reset();
    if(std::strcmp(argv[1],"valid")!=0)return 2;
    std::cout<<"PASS cross-frame lifetime, birth-site/destruction-phase ownership, teardown=0\n";
    return 0;
}
