// SPDX-License-Identifier: MIT
#define SDL_MAIN_HANDLED
#include <SDL.h>
#include "renderer_state.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <type_traits>
#include <vector>

static_assert(!std::is_copy_constructible_v<scoped_sdl_clipst>);
static_assert(!std::is_copy_constructible_v<scoped_sdl_colorst>);
static_assert(!std::is_copy_constructible_v<scoped_render_originst>);
static_assert(!std::is_move_constructible_v<scoped_sdl_clipst>);

uint64_t state_checks=0,pixel_checks=0,cases=0;
void require(bool result,const char *label)
{
    if(!result){std::cerr<<"FAIL "<<label<<" SDL="<<SDL_GetError()<<"\n";std::exit(1);}
}
bool equal_rect(const SDL_Rect &a,const SDL_Rect &b)
{
    return a.x==b.x&&a.y==b.y&&a.w==b.w&&a.h==b.h;
}
struct state_snapshotst
{
    SDL_bool enabled;
    SDL_Rect clip{},viewport{};
    std::array<Uint8,4> color{};
    SDL_BlendMode blend;
    float scale_x=0,scale_y=0;
    SDL_Texture *target=nullptr;
    explicit state_snapshotst(SDL_Renderer *r):enabled(SDL_RenderIsClipEnabled(r))
    {
        SDL_RenderGetClipRect(r,&clip);SDL_RenderGetViewport(r,&viewport);
        SDL_RenderGetScale(r,&scale_x,&scale_y);target=SDL_GetRenderTarget(r);
        require(SDL_GetRenderDrawColor(r,&color[0],&color[1],&color[2],&color[3])==0,"get color");
        require(SDL_GetRenderDrawBlendMode(r,&blend)==0,"get blend mode");
    }
    void expect(SDL_Renderer *r)const
    {
        const state_snapshotst after(r);
        require(enabled==after.enabled&&equal_rect(clip,after.clip),"restore clip enabled+rectangle");
        require(color==after.color,"restore draw RGBA");
        require(equal_rect(viewport,after.viewport)&&blend==after.blend&&
            scale_x==after.scale_x&&scale_y==after.scale_y&&target==after.target,
            "preserve viewport/scale/blend/target");
        ++state_checks;
    }
};
struct canvasst
{
    static constexpr int width=64,height=64;
    SDL_Surface *surface=nullptr;
    SDL_Renderer *renderer=nullptr;
    explicit canvasst(float scale=1.0f)
    {
        surface=SDL_CreateRGBSurfaceWithFormat(0,width,height,32,SDL_PIXELFORMAT_ARGB8888);
        require(surface!=nullptr,"create ARGB8888 surface");
        renderer=SDL_CreateSoftwareRenderer(surface);require(renderer!=nullptr,"create software renderer");
        require(SDL_RenderGetWindow(renderer)==nullptr,"offscreen renderer has no window");
        SDL_RendererInfo info{};require(SDL_GetRendererInfo(renderer,&info)==0,"renderer info");
        require((info.flags&SDL_RENDERER_SOFTWARE)!=0,"actual software renderer");
        require(SDL_RenderSetScale(renderer,scale,scale)==0,"set fixture scale");
        const SDL_Rect viewport{1,2,25,23};
        require(SDL_RenderSetViewport(renderer,&viewport)==0,"set fixture viewport");
        require(SDL_SetRenderDrawBlendMode(renderer,SDL_BLENDMODE_NONE)==0,"set fixture blend");
        require(SDL_SetRenderDrawColor(renderer,17,61,93,149)==0,"seed RGBA");
    }
    ~canvasst(){SDL_DestroyRenderer(renderer);SDL_FreeSurface(surface);}
    canvasst(const canvasst &)=delete;
    canvasst &operator=(const canvasst &)=delete;

    std::vector<Uint32> footprint()
    {
        // Clear intentionally initializes the entire surface; FillRect is the operation
        // whose clipping behavior is measured. Clear itself does not honor clipping.
        Uint8 r,g,b,a;require(SDL_GetRenderDrawColor(renderer,&r,&g,&b,&a)==0,"footprint color");
        require(SDL_SetRenderDrawColor(renderer,0,0,0,0)==0,"clear color");
        require(SDL_RenderClear(renderer)==0,"clear surface");
        require(SDL_SetRenderDrawColor(renderer,r,g,b,a)==0,"restore footprint color");
        require(SDL_RenderFillRect(renderer,nullptr)==0,"draw clipped fill");
        require(SDL_RenderFlush(renderer)==0,"flush software pixels");
        require(SDL_LockSurface(surface)==0,"lock surface readback");
        std::vector<Uint32> pixels(size_t(width)*height);
        for(int y=0;y<height;++y)
            std::memcpy(pixels.data()+size_t(y)*width,
                static_cast<const Uint8 *>(surface->pixels)+size_t(y)*surface->pitch,width*sizeof(Uint32));
        SDL_UnlockSurface(surface);return pixels;
    }
};
void expect_pixels(const std::vector<Uint32> &before,const std::vector<Uint32> &after)
{
    require(before==after,"restored clip produces identical pixels");pixel_checks+=before.size();
}
void exercise_scope(canvasst &canvas,int32_t &origin_x,int32_t &origin_y,bool nested,bool early_return)
{
    const SDL_Rect replacement{12,11,4,6};
    const scoped_sdl_clipst clip(canvas.renderer,SDL_RenderSetClipRect,SDL_RenderGetClipRect,SDL_RenderIsClipEnabled);
    require(SDL_RenderSetClipRect(canvas.renderer,&replacement)==0,"replace clip");
    SDL_Rect active{};SDL_RenderGetClipRect(canvas.renderer,&active);
    require(SDL_RenderIsClipEnabled(canvas.renderer)&&equal_rect(active,replacement),"temporary replacement clip");
    const auto replacement_pixels=canvas.footprint();
    require(std::count_if(replacement_pixels.begin(),replacement_pixels.end(),[](Uint32 p){return p!=0;})>0,
        "replacement draws even when incoming clip is empty/disjoint");
    const state_snapshotst outer(canvas.renderer);
    {
        const scoped_sdl_colorst color(canvas.renderer,SDL_SetRenderDrawColor,SDL_GetRenderDrawColor);
        require(color.captured,"capture color before black fill");
        require(SDL_SetRenderDrawColor(canvas.renderer,0,0,0,255)==0,"temporary black");
        require(SDL_RenderFillRect(canvas.renderer,&replacement)==0,"black fill");
    }
    outer.expect(canvas.renderer); // engine repaint must see the caller's color already restored
    const scoped_render_originst origin(origin_x,origin_y);
    origin_x+=9;origin_y-=7;
    if(nested)
    {
        const int32_t outer_x=origin_x,outer_y=origin_y;
        {
            const scoped_sdl_clipst inner_clip(canvas.renderer,SDL_RenderSetClipRect,SDL_RenderGetClipRect,SDL_RenderIsClipEnabled);
            const scoped_sdl_colorst inner_color(canvas.renderer,SDL_SetRenderDrawColor,SDL_GetRenderDrawColor);
            const scoped_render_originst inner_origin(origin_x,origin_y);
            const SDL_Rect inner_rect{6,8,3,4};
            require(SDL_RenderSetClipRect(canvas.renderer,&inner_rect)==0,"nested replacement");
            require(SDL_SetRenderDrawColor(canvas.renderer,203,151,79,31)==0,"nested RGBA");
            origin_x=-123;origin_y=456;
        }
        require(origin_x==outer_x&&origin_y==outer_y,"nested origin restoration");
        outer.expect(canvas.renderer);expect_pixels(replacement_pixels,canvas.footprint());
    }
    if(early_return)return;
    require(origin_x==82&&origin_y==-48,"temporary origin visible inside scope");
}
void stable_scale_cases()
{
    for(float scale:{1.0f,1.25f,2.0f})for(int kind=0;kind<6;++kind)
        for(int mode=0;mode<3;++mode)
        {
            canvasst canvas(scale);
            // Replacement is {12,11,4,6}: cover disabled, disjoint, empty,
            // incoming-contains-map, map-contains-incoming, and partial overlap.
            const std::array<SDL_Rect,6> initial_clips{{
                {3,3,5,5},{3,3,5,5},{3,3,0,5},
                {8,8,15,14},{13,12,2,3},{10,10,5,5}}};
            const SDL_Rect initial=initial_clips[size_t(kind)];
            require(SDL_RenderSetClipRect(canvas.renderer,kind==0?nullptr:&initial)==0,"initial clip");
            const state_snapshotst before(canvas.renderer);const auto pixels=canvas.footprint();
            require(before.enabled==(kind==0?SDL_FALSE:SDL_TRUE),"seed enabled/disabled including empty clip");
            if(kind==2)require(equal_rect(before.clip,initial)&&
                std::all_of(pixels.begin(),pixels.end(),[](Uint32 p){return p==0;}),"enabled empty clip draws no pixels");
            int32_t origin_x=73,origin_y=-41;
            exercise_scope(canvas,origin_x,origin_y,mode==1,mode==2);
            require(origin_x==73&&origin_y==-41,"restore origin after scope/early return");
            before.expect(canvas.renderer);expect_pixels(pixels,canvas.footprint());++cases;
        }
}
int SDLCALL failed_color_getter(SDL_Renderer *,Uint8 *,Uint8 *,Uint8 *,Uint8 *){return -1;}
void color_capture_failure()
{
    canvasst canvas;const state_snapshotst before(canvas.renderer);
    const auto try_fill=[&]() {
        const scoped_sdl_clipst clip(canvas.renderer,SDL_RenderSetClipRect,SDL_RenderGetClipRect,SDL_RenderIsClipEnabled);
        const SDL_Rect temporary{12,11,4,6};
        require(SDL_RenderSetClipRect(canvas.renderer,&temporary)==0,"failed-color path temporary clip");
        const scoped_sdl_colorst color(canvas.renderer,SDL_SetRenderDrawColor,failed_color_getter);
        require(!color.captured,"failed capture is explicitly unavailable");
        if(!color.captured)return;
        require(false,"must not draw after failed color capture");
    };
    try_fill();
    before.expect(canvas.renderer);++cases;
}
void unsupported_scale_diagnostics()
{
    // Intentional contract violation: the incoming clip was established at an older scale.
    canvasst historical;
    const SDL_Rect initial{3,3,5,5},replacement{12,11,4,6};
    require(SDL_RenderSetClipRect(historical.renderer,&initial)==0,"diagnostic initial clip");
    require(SDL_RenderSetScale(historical.renderer,2,2)==0,"diagnostic historical scale change");
    const state_snapshotst before(historical.renderer);const auto pixels=historical.footprint();
    {const scoped_sdl_clipst clip(historical.renderer,SDL_RenderSetClipRect,SDL_RenderGetClipRect,SDL_RenderIsClipEnabled);
        require(SDL_RenderSetClipRect(historical.renderer,&replacement)==0,"diagnostic replacement");}
    before.expect(historical.renderer);
    require(pixels!=historical.footprint(),"old-scale hidden pixel state is not recoverable by integer get/set");
    std::cout<<"DIAGNOSTIC old_scale_clip public_state_equal=1 pixels_equal=0 supported=0\n";

    // A scale mutation during the guard is also outside its contract.
    canvasst during;require(SDL_RenderSetClipRect(during.renderer,&initial)==0,"during-scope initial clip");
    const auto during_pixels=during.footprint();
    {const scoped_sdl_clipst clip(during.renderer,SDL_RenderSetClipRect,SDL_RenderGetClipRect,SDL_RenderIsClipEnabled);
        require(SDL_RenderSetClipRect(during.renderer,&replacement)==0,"during-scope replacement");
        require(SDL_RenderSetScale(during.renderer,2,2)==0,"intentional during-scope scale violation");}
    SDL_Rect after{};SDL_RenderGetClipRect(during.renderer,&after);
    require(equal_rect(initial,after)&&during_pixels!=during.footprint(),"during-scope scale pixel mismatch observed");
    std::cout<<"DIAGNOSTIC scale_changed_during_scope public_rect_equal=1 pixels_equal=0 supported=0\n";
}
int main()
{
    require(SDL_Init(0)==0,"initialize without video subsystem");
    SDL_version version{};SDL_GetVersion(&version);
    require(version.major==2&&version.minor==26&&version.patch==2,"pinned SDL2.26.2 runtime");
    stable_scale_cases();color_capture_failure();unsupported_scale_diagnostics();
    SDL_Quit();
    std::cout<<"PASS SDL=2.26.2 windows_created=0 stable_scales=3 clip_relations=6 cases="<<cases
        <<" state_checks="<<state_checks<<" pixel_checks="<<pixel_checks<<" unsupported_scale_diagnostics=2\n";
}
