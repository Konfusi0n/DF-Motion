// SPDX-License-Identifier: MIT

#ifndef RENDERER_STATE_H
#define RENDERER_STATE_H

#include <SDL_render.h>
#include <cstdint>

// Restore the public SDL clip-enabled flag and rectangle. The incoming clip must
// have been set at the current renderer scale, and that scale must remain unchanged
// throughout this scope. SDL2's integer getter cannot recover hidden fractional
// clip coordinates after a scale change. This guard never changes renderer scale.
struct scoped_sdl_clipst
{
	SDL_Renderer *renderer;
	decltype(&SDL_RenderSetClipRect) set_clip;
	SDL_bool enabled;
	SDL_Rect rect{};

	scoped_sdl_clipst(SDL_Renderer *r,
		decltype(&SDL_RenderSetClipRect) set,
		decltype(&SDL_RenderGetClipRect) get,
		decltype(&SDL_RenderIsClipEnabled) is_enabled):
		renderer(r),set_clip(set),enabled(is_enabled(r))
		{
		get(renderer,&rect);
		}

	~scoped_sdl_clipst() noexcept
		{
		set_clip(renderer,enabled?&rect:nullptr);
		}

	scoped_sdl_clipst(const scoped_sdl_clipst &)=delete;
	scoped_sdl_clipst &operator=(const scoped_sdl_clipst &)=delete;
};

struct scoped_sdl_colorst
{
	SDL_Renderer *renderer;
	decltype(&SDL_SetRenderDrawColor) set_color;
	Uint8 red=0,green=0,blue=0,alpha=255;
	bool captured=false;

	scoped_sdl_colorst(SDL_Renderer *r,
		decltype(&SDL_SetRenderDrawColor) set,
		decltype(&SDL_GetRenderDrawColor) get):renderer(r),set_color(set)
		{
		captured=get(renderer,&red,&green,&blue,&alpha)==0;
		}

	~scoped_sdl_colorst() noexcept
		{
		if(captured)set_color(renderer,red,green,blue,alpha);
		}

	scoped_sdl_colorst(const scoped_sdl_colorst &)=delete;
	scoped_sdl_colorst &operator=(const scoped_sdl_colorst &)=delete;
};

struct scoped_render_originst
{
	int32_t &x,&y;
	int32_t saved_x,saved_y;

	scoped_render_originst(int32_t &origin_x,int32_t &origin_y):
		x(origin_x),y(origin_y),saved_x(origin_x),saved_y(origin_y){}

	~scoped_render_originst() noexcept
		{
		x=saved_x;y=saved_y;
		}

	scoped_render_originst(const scoped_render_originst &)=delete;
	scoped_render_originst &operator=(const scoped_render_originst &)=delete;
};

#endif
