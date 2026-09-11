// SPDX-License-Identifier: MIT
// Diagnostic executable only. No part of this header is compiled into clean runs.
#ifndef DF_MOTION_ATTRIBUTION_PROBE_H
#define DF_MOTION_ATTRIBUTION_PROBE_H

namespace attribution_probe {
using clock_type=std::chrono::steady_clock;
inline uint64_t now(){return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(clock_type::now().time_since_epoch()).count());}
enum class Phase:uint8_t { synchronization,candidate_generation,sort_unique,moving_proxy,
    center_anchor,resting_mirrored,texture_adapter,coverage,returned_destruction,
    collector_other,teardown,allocator_call,count };
constexpr std::array<const char *,12> phase_names={"synchronization","candidate_generation","sort_unique",
    "moving_proxy","center_anchor","resting_mirrored","texture_adapter","coverage",
    "returned_destruction","collector_other","teardown","allocator_call"};
constexpr size_t max_sites=64,max_sizes=64,max_depth=32;
struct SizeCount {size_t size=0;uint64_t count=0;};
struct Statistics {
    uint64_t inclusive_ns=0,exclusive_ns=0,calls=0;
    uint64_t allocations=0,requested_bytes=0,backing_bytes=0,frees=0,freed_bytes=0;
    uint64_t malloc_ns=0,free_ns=0,peak_live_bytes=0;
    uint64_t lifetimes=0,lifetime_ns_sum=0,lifetime_ns_min=UINT64_MAX,lifetime_ns_max=0;
    uint64_t same_frame_frees=0,lifetime_frames_max=0;
    std::array<uint64_t,size_t(Phase::count)> allocation_phase_counts{},free_phase_counts{};
    std::array<SizeCount,max_sizes> sizes{};
    size_t size_count=0;
};
inline std::array<Statistics,max_sites> sites{};
inline std::array<Statistics,size_t(Phase::count)> phases{};
inline std::array<uint64_t,max_sites> site_live{};
inline std::array<uint64_t,size_t(Phase::count)> phase_live{};
struct StackEntry {uint64_t start=0,children=0;Phase phase=Phase::collector_other;};
inline std::array<StackEntry,max_depth> stack{};
inline size_t depth=0,current_site=0;
inline Phase current_phase=Phase::collector_other;
inline int current_frame=0;
inline const char *engine_name="unset",*workload_name="unset",*frame_kind="frame";
inline int viewport_count=0,trial_number=0,run_order=0;
[[noreturn]] inline void fail(const char *message){std::cerr<<"ATTRIBUTION_FAILURE "<<message<<'\n';std::exit(4);}

struct SiteScope {
    size_t previous;bool active=true;
    explicit SiteScope(size_t site):previous(current_site){if(site>=max_sites)fail("site overflow");current_site=site;}
    void finish(){if(active){current_site=previous;active=false;}}
    ~SiteScope(){finish();}
    SiteScope(const SiteScope&)=delete;SiteScope&operator=(const SiteScope&)=delete;
};
struct Scope {
    Phase previous;size_t previous_site;bool active=true;
    Scope(Phase phase,size_t site):previous(current_phase),previous_site(current_site) {
        if(depth==max_depth||site>=max_sites)fail("scope overflow");
        current_phase=phase;current_site=site;stack[depth++]={now(),0,phase};
    }
    void finish() {
        if(!active)return;
        const uint64_t end=now();if(!depth)fail("scope underflow");
        const auto entry=stack[--depth];const uint64_t elapsed=end-entry.start;
        if(entry.children>elapsed)fail("nested timing exceeds parent");
        auto &stats=phases[size_t(entry.phase)];stats.inclusive_ns+=elapsed;
        stats.exclusive_ns+=elapsed-entry.children;++stats.calls;
        if(depth)stack[depth-1].children+=elapsed;
        current_phase=previous;current_site=previous_site;active=false;
    }
    ~Scope(){finish();}
    Scope(const Scope&)=delete;Scope&operator=(const Scope&)=delete;
};
inline void record_allocator_child(uint64_t elapsed) {
    auto &stats=phases[size_t(Phase::allocator_call)];stats.inclusive_ns+=elapsed;
    stats.exclusive_ns+=elapsed;++stats.calls;
    if(depth)stack[depth-1].children+=elapsed;
}
inline void add_size(Statistics &stats,size_t size) {
    for(size_t i=0;i<stats.size_count;++i)if(stats.sizes[i].size==size){++stats.sizes[i].count;return;}
    if(stats.size_count==max_sizes)fail("allocation-size histogram overflow");
    stats.sizes[stats.size_count++]={size,1};
}
inline double median_size(const Statistics &stats) {
    if(!stats.allocations)return 0;
    auto entries=stats.sizes;
    std::sort(entries.begin(),entries.begin()+stats.size_count,[](const auto&a,const auto&b){return a.size<b.size;});
    uint64_t sum=0;size_t left=0,right=0;
    const uint64_t l=(stats.allocations-1)/2,r=stats.allocations/2;
    for(size_t i=0;i<stats.size_count;++i){const uint64_t next=sum+entries[i].count;
        if(l>=sum&&l<next)left=entries[i].size;if(r>=sum&&r<next)right=entries[i].size;sum=next;}
    return (double(left)+double(right))/2;
}
inline void begin_trial(const char *engine,const char *workload,int viewports,int trial,int order) {
    for(auto value:site_live)if(value)fail("live site bytes survived trial");
    for(auto value:phase_live)if(value)fail("live phase bytes survived trial");
    engine_name=engine;workload_name=workload;viewport_count=viewports;trial_number=trial;run_order=order;
}
inline void begin_frame(int frame,const char *kind="frame") {
    if(depth)fail("unclosed scope at frame boundary");
    sites={};phases={};current_frame=frame;frame_kind=kind;current_site=0;current_phase=Phase::collector_other;
    for(size_t i=0;i<sites.size();++i)sites[i].peak_live_bytes=site_live[i];
    for(size_t i=0;i<phases.size();++i)phases[i].peak_live_bytes=phase_live[i];
}
inline void write_stats(const char *type,size_t id,const Statistics &stats,uint64_t live) {
    std::cerr<<"{\"type\":\""<<type<<"\",\"engine\":\""<<engine_name<<"\",\"workload\":\""<<workload_name
        <<"\",\"viewports\":"<<viewport_count<<",\"trial\":"<<trial_number<<",\"order\":"<<run_order
        <<",\"frame\":"<<current_frame<<",\"kind\":\""<<frame_kind<<"\",\"id\":"<<id;
    if(type[0]=='p')std::cerr<<",\"phase\":\""<<phase_names[id]<<'"';
    std::cerr<<",\"inclusive_ns\":"<<stats.inclusive_ns<<",\"exclusive_ns\":"<<stats.exclusive_ns
        <<",\"calls\":"<<stats.calls<<",\"allocations\":"<<stats.allocations<<",\"requested_bytes\":"<<stats.requested_bytes
        <<",\"backing_bytes\":"<<stats.backing_bytes<<",\"frees\":"<<stats.frees<<",\"freed_bytes\":"<<stats.freed_bytes
        <<",\"malloc_ns\":"<<stats.malloc_ns<<",\"free_ns\":"<<stats.free_ns<<",\"live_bytes\":"<<live
        <<",\"peak_live_bytes\":"<<stats.peak_live_bytes<<",\"median_allocation_size\":"<<median_size(stats)
        <<",\"lifetimes\":"<<stats.lifetimes<<",\"lifetime_ns_sum\":"<<stats.lifetime_ns_sum
        <<",\"lifetime_ns_min\":"<<(stats.lifetimes?stats.lifetime_ns_min:0)<<",\"lifetime_ns_max\":"<<stats.lifetime_ns_max
        <<",\"same_frame_frees\":"<<stats.same_frame_frees<<",\"lifetime_frames_max\":"<<stats.lifetime_frames_max
        <<",\"size_histogram\":[";
    for(size_t i=0;i<stats.size_count;++i){if(i)std::cerr<<',';std::cerr<<'['<<stats.sizes[i].size<<','<<stats.sizes[i].count<<']';}
    std::cerr<<"],\"allocation_phase_counts\":[";
    for(size_t i=0;i<stats.allocation_phase_counts.size();++i){if(i)std::cerr<<',';std::cerr<<stats.allocation_phase_counts[i];}
    std::cerr<<"],\"free_phase_counts\":[";
    for(size_t i=0;i<stats.free_phase_counts.size();++i){if(i)std::cerr<<',';std::cerr<<stats.free_phase_counts[i];}
    std::cerr<<"]}\n";
}
inline void emit_frame(uint64_t expected_allocations,uint64_t expected_bytes,uint64_t expected_live) {
    if(depth)fail("unclosed scope at output");
    uint64_t site_allocations=0,site_bytes=0,phase_allocations=0,phase_bytes=0,live=0;
    for(size_t i=0;i<sites.size();++i){site_allocations+=sites[i].allocations;site_bytes+=sites[i].requested_bytes;live+=site_live[i];}
    for(const auto &phase:phases){phase_allocations+=phase.allocations;phase_bytes+=phase.requested_bytes;}
    if(site_allocations!=expected_allocations||phase_allocations!=expected_allocations||
        site_bytes!=expected_bytes||phase_bytes!=expected_bytes||live!=expected_live)fail("allocation totals do not reconcile");
    if(sites[0].allocations)fail("unattributed allocation");
    for(size_t i=0;i<phases.size();++i)write_stats("phase",i,phases[i],phase_live[i]);
    for(size_t i=0;i<sites.size();++i)if(sites[i].allocations||sites[i].frees||site_live[i])write_stats("site",i,sites[i],site_live[i]);
}
inline void calibration() {
    std::array<uint64_t,2048> samples{};
    for(auto &sample:samples){const auto start=now();const auto end=now();sample=end-start;}
    std::sort(samples.begin(),samples.end());
    std::cerr<<"{\"type\":\"calibration\",\"name\":\"clock_pair\",\"samples\":2048,\"median_ns\":"
        <<(samples[1023]+samples[1024])/2.0<<",\"p95_ns\":"<<samples[1945]<<",\"p99_ns\":"<<samples[2027]<<",\"worst_ns\":"<<samples.back()<<"}\n";
    for(auto &sample:samples){const auto start=now();{Scope scope(Phase::collector_other,1);}sample=now()-start;}
    std::sort(samples.begin(),samples.end());
    std::cerr<<"{\"type\":\"calibration\",\"name\":\"empty_scope\",\"samples\":2048,\"median_ns\":"
        <<(samples[1023]+samples[1024])/2.0<<",\"p95_ns\":"<<samples[1945]<<",\"p99_ns\":"<<samples[2027]<<",\"worst_ns\":"<<samples.back()<<"}\n";
    begin_frame(0);
}
} // namespace attribution_probe

namespace allocation_probe {
struct Header {void *base;size_t size;uint64_t generation,born_ns;int born_frame;uint16_t site,phase;};
inline uint64_t generation=1,allocations=0,allocated_bytes=0,live_bytes=0,peak_bytes=0;
inline bool enabled=false;
inline void *allocate(size_t size,size_t alignment) {
    alignment=std::max(alignment,alignof(Header));
    if(size>std::numeric_limits<size_t>::max()-alignment-sizeof(Header))throw std::bad_alloc();
    const size_t backing=size+alignment+sizeof(Header);
    const auto start=enabled?attribution_probe::now():0;
    void *base=std::malloc(backing);
    const auto end=enabled?attribution_probe::now():0;
    if(!base)throw std::bad_alloc();
    const uintptr_t first=reinterpret_cast<uintptr_t>(base)+sizeof(Header);
    const uintptr_t aligned=(first+alignment-1)&~(uintptr_t(alignment)-1);
    auto *header=reinterpret_cast<Header *>(aligned)-1;
    *header={base,size,enabled?generation:0,end,attribution_probe::current_frame,
        uint16_t(attribution_probe::current_site),uint16_t(attribution_probe::current_phase)};
    if(enabled) {
        ++allocations;allocated_bytes+=size;live_bytes+=size;peak_bytes=std::max(peak_bytes,live_bytes);
        const auto elapsed=end-start;attribution_probe::record_allocator_child(elapsed);
        auto &site=attribution_probe::sites[header->site];auto &phase=attribution_probe::phases[header->phase];
        attribution_probe::site_live[header->site]+=size;attribution_probe::phase_live[header->phase]+=size;
        for(auto *stats:{&site,&phase}){++stats->allocations;++stats->allocation_phase_counts[header->phase];stats->requested_bytes+=size;stats->backing_bytes+=backing;stats->malloc_ns+=elapsed;attribution_probe::add_size(*stats,size);}
        site.peak_live_bytes=std::max(site.peak_live_bytes,attribution_probe::site_live[header->site]);
        phase.peak_live_bytes=std::max(phase.peak_live_bytes,attribution_probe::phase_live[header->phase]);
    }
    return reinterpret_cast<void *>(aligned);
}
inline void release(void *value) noexcept {
    if(!value)return;
    const auto header=*(static_cast<Header *>(value)-1);
    const bool tracked=header.generation==generation;
    const auto start=tracked?attribution_probe::now():0;
    std::free(header.base);
    const auto end=tracked?attribution_probe::now():0;
    if(tracked) {
        live_bytes-=header.size;attribution_probe::site_live[header.site]-=header.size;
        attribution_probe::phase_live[header.phase]-=header.size;
        const auto elapsed=end-start,life=end-header.born_ns;
        attribution_probe::record_allocator_child(elapsed);
        // Site attribution follows birth ownership; phase attribution identifies destruction work.
        auto &site=attribution_probe::sites[header.site];auto &phase=attribution_probe::phases[size_t(attribution_probe::current_phase)];
        for(auto *stats:{&site,&phase}){++stats->frees;++stats->free_phase_counts[size_t(attribution_probe::current_phase)];stats->freed_bytes+=header.size;stats->free_ns+=elapsed;
            ++stats->lifetimes;stats->lifetime_ns_sum+=life;stats->lifetime_ns_min=std::min(stats->lifetime_ns_min,life);
            stats->lifetime_ns_max=std::max(stats->lifetime_ns_max,life);stats->same_frame_frees+=header.born_frame==attribution_probe::current_frame;
            stats->lifetime_frames_max=std::max(stats->lifetime_frames_max,uint64_t(attribution_probe::current_frame-header.born_frame));}
    }
}
inline void reset(){if(live_bytes)attribution_probe::fail("tracked bytes survived teardown");++generation;allocations=allocated_bytes=live_bytes=peak_bytes=0;}
} // namespace allocation_probe

void *operator new(size_t size){return allocation_probe::allocate(size,alignof(std::max_align_t));}
void *operator new[](size_t size){return ::operator new(size);}
void operator delete(void *value)noexcept{allocation_probe::release(value);}
void operator delete[](void *value)noexcept{allocation_probe::release(value);}
void operator delete(void *value,size_t)noexcept{allocation_probe::release(value);}
void operator delete[](void *value,size_t)noexcept{allocation_probe::release(value);}
void *operator new(size_t size,std::align_val_t alignment){return allocation_probe::allocate(size,size_t(alignment));}
void *operator new[](size_t size,std::align_val_t alignment){return ::operator new(size,alignment);}
void operator delete(void *value,std::align_val_t)noexcept{allocation_probe::release(value);}
void operator delete[](void *value,std::align_val_t)noexcept{allocation_probe::release(value);}
void operator delete(void *value,size_t,std::align_val_t)noexcept{allocation_probe::release(value);}
void operator delete[](void *value,size_t,std::align_val_t)noexcept{allocation_probe::release(value);}

#endif
