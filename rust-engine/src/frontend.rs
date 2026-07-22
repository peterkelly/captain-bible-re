//! SDL3 window frontend.
//!
//! This module intentionally binds the small SDL surface it needs directly,
//! keeping the engine core free of third-party Rust dependencies.

mod ui;

use crate::engine::{Engine, EngineEvent, InputEvent, ReferenceTimer};
use crate::error::{EngineError, Result};
use crate::graphics::{SCREEN_HEIGHT, SCREEN_WIDTH};
use std::ffi::{CStr, c_char, c_int, c_void};
use std::ptr;
use ui::{
    DISPLAY_HEIGHT, DISPLAY_SCALE, DISPLAY_WIDTH, StatusBarState, StatusControl, UiAssets, UiState,
    draw_scene_overlays, status_control_at,
};

const SDL_INIT_VIDEO: u32 = 0x20;
const SDL_WINDOW_RESIZABLE: u64 = 0x20;
const SDL_EVENT_QUIT: u32 = 0x100;
const SDL_PIXELFORMAT_ARGB8888: u32 = 0x1636_2004;
const SDL_TEXTUREACCESS_STREAMING: c_int = 1;
const SDL_LOGICAL_PRESENTATION_LETTERBOX: c_int = 2;
const SDL_SCALEMODE_NEAREST: c_int = 0;

#[repr(C)]
struct SdlWindow(c_void);
#[repr(C)]
struct SdlRenderer(c_void);
#[repr(C)]
struct SdlTexture(c_void);

#[repr(C, align(8))]
struct SdlEvent {
    bytes: [u8; 128],
}

impl SdlEvent {
    fn event_type(&self) -> u32 {
        u32::from_ne_bytes(self.bytes[0..4].try_into().unwrap())
    }
}

unsafe extern "C" {
    fn SDL_Init(flags: u32) -> bool;
    fn SDL_Quit();
    fn SDL_GetError() -> *const c_char;
    fn SDL_CreateWindowAndRenderer(
        title: *const c_char,
        width: c_int,
        height: c_int,
        flags: u64,
        window: *mut *mut SdlWindow,
        renderer: *mut *mut SdlRenderer,
    ) -> bool;
    fn SDL_DestroyWindow(window: *mut SdlWindow);
    fn SDL_DestroyRenderer(renderer: *mut SdlRenderer);
    fn SDL_CreateTexture(
        renderer: *mut SdlRenderer,
        format: u32,
        access: c_int,
        width: c_int,
        height: c_int,
    ) -> *mut SdlTexture;
    fn SDL_DestroyTexture(texture: *mut SdlTexture);
    fn SDL_SetTextureScaleMode(texture: *mut SdlTexture, mode: c_int) -> bool;
    fn SDL_SetRenderLogicalPresentation(
        renderer: *mut SdlRenderer,
        width: c_int,
        height: c_int,
        mode: c_int,
    ) -> bool;
    fn SDL_RenderCoordinatesFromWindow(
        renderer: *mut SdlRenderer,
        window_x: f32,
        window_y: f32,
        x: *mut f32,
        y: *mut f32,
    ) -> bool;
    fn SDL_UpdateTexture(
        texture: *mut SdlTexture,
        rect: *const c_void,
        pixels: *const c_void,
        pitch: c_int,
    ) -> bool;
    fn SDL_RenderClear(renderer: *mut SdlRenderer) -> bool;
    fn SDL_RenderTexture(
        renderer: *mut SdlRenderer,
        texture: *mut SdlTexture,
        source: *const c_void,
        destination: *const c_void,
    ) -> bool;
    fn SDL_RenderPresent(renderer: *mut SdlRenderer) -> bool;
    fn SDL_PollEvent(event: *mut SdlEvent) -> bool;
    fn SDL_GetKeyboardState(count: *mut c_int) -> *const bool;
    fn SDL_GetMouseState(x: *mut f32, y: *mut f32) -> u32;
    fn SDL_GetTicks() -> u64;
    fn SDL_Delay(milliseconds: u32);
}

struct Sdl {
    window: *mut SdlWindow,
    renderer: *mut SdlRenderer,
    texture: *mut SdlTexture,
}

impl Drop for Sdl {
    fn drop(&mut self) {
        unsafe {
            SDL_DestroyTexture(self.texture);
            SDL_DestroyRenderer(self.renderer);
            SDL_DestroyWindow(self.window);
            SDL_Quit();
        }
    }
}

impl Sdl {
    fn open() -> Result<Self> {
        unsafe {
            if !SDL_Init(SDL_INIT_VIDEO) {
                return Err(sdl_error("SDL_Init"));
            }
            let mut window = ptr::null_mut();
            let mut renderer = ptr::null_mut();
            if !SDL_CreateWindowAndRenderer(
                c"Captain Bible".as_ptr(),
                (SCREEN_WIDTH * 3) as c_int,
                (SCREEN_HEIGHT * 3) as c_int,
                SDL_WINDOW_RESIZABLE,
                &mut window,
                &mut renderer,
            ) {
                SDL_Quit();
                return Err(sdl_error("SDL_CreateWindowAndRenderer"));
            }
            let texture = SDL_CreateTexture(
                renderer,
                SDL_PIXELFORMAT_ARGB8888,
                SDL_TEXTUREACCESS_STREAMING,
                DISPLAY_WIDTH as c_int,
                DISPLAY_HEIGHT as c_int,
            );
            if texture.is_null() {
                SDL_DestroyRenderer(renderer);
                SDL_DestroyWindow(window);
                SDL_Quit();
                return Err(sdl_error("SDL_CreateTexture"));
            }
            if !SDL_SetTextureScaleMode(texture, SDL_SCALEMODE_NEAREST)
                || !SDL_SetRenderLogicalPresentation(
                    renderer,
                    DISPLAY_WIDTH as c_int,
                    DISPLAY_HEIGHT as c_int,
                    SDL_LOGICAL_PRESENTATION_LETTERBOX,
                )
            {
                SDL_DestroyTexture(texture);
                SDL_DestroyRenderer(renderer);
                SDL_DestroyWindow(window);
                SDL_Quit();
                return Err(sdl_error("SDL renderer configuration"));
            }
            Ok(Self {
                window,
                renderer,
                texture,
            })
        }
    }

    fn present(&self, engine: &Engine, ui: &UiState, ui_assets: &UiAssets) -> Result<()> {
        let colors = engine.palette().rgba8888();
        let mut pixels = vec![0; DISPLAY_WIDTH * DISPLAY_HEIGHT];
        for (source_y, row) in engine
            .framebuffer()
            .pixels()
            .chunks_exact(SCREEN_WIDTH)
            .enumerate()
        {
            for (source_x, &index) in row.iter().enumerate() {
                let color = colors[index as usize];
                let destination_x = source_x * DISPLAY_SCALE;
                let destination_y = source_y * DISPLAY_SCALE;
                for y in 0..DISPLAY_SCALE {
                    let offset = (destination_y + y) * DISPLAY_WIDTH + destination_x;
                    pixels[offset..offset + DISPLAY_SCALE].fill(color);
                }
            }
        }
        draw_scene_overlays(&mut pixels, ui_assets, &colors, status_bar_state(engine));
        ui.draw(&mut pixels, ui_assets, &colors);
        unsafe {
            if !SDL_UpdateTexture(
                self.texture,
                ptr::null(),
                pixels.as_ptr().cast(),
                (DISPLAY_WIDTH * 4) as c_int,
            ) || !SDL_RenderClear(self.renderer)
                || !SDL_RenderTexture(self.renderer, self.texture, ptr::null(), ptr::null())
                || !SDL_RenderPresent(self.renderer)
            {
                return Err(sdl_error("SDL rendering"));
            }
        }
        Ok(())
    }
}

pub fn run_sdl(engine: &mut Engine) -> Result<()> {
    let ui_assets = UiAssets::load(engine.archive())?;
    let sdl = Sdl::open()?;
    let mut ui = UiState::default();
    let mut previous_keys = vec![false; 512];
    let mut previous_buttons = 0u32;
    let mut previous_pointer = None;
    let mut previous_tick = unsafe { SDL_GetTicks() };
    let mut reference_timer = ReferenceTimer::default();
    loop {
        let mut event = SdlEvent { bytes: [0; 128] };
        unsafe {
            while SDL_PollEvent(&mut event) {
                if event.event_type() == SDL_EVENT_QUIT {
                    return Ok(());
                }
            }
        }
        let mut inputs = Vec::new();
        let mut key_count = 0;
        let keys = unsafe {
            std::slice::from_raw_parts(SDL_GetKeyboardState(&mut key_count), key_count as usize)
        };
        let rising =
            |scan: usize| keys.get(scan) == Some(&true) && previous_keys.get(scan) != Some(&true);
        if rising(40) {
            if let Some(input) = ui.activate() {
                inputs.push(input);
            } else {
                inputs.push(InputEvent::Confirm);
            }
        }
        if rising(41) {
            if let Some(input) = ui.cancel() {
                inputs.push(input);
            } else if !ui.choices_active() {
                inputs.push(InputEvent::Cancel);
            }
        }
        if !ui.modal_active() && engine.status_controls_visible() {
            for (scan, control) in [
                (58, StatusControl::Bible),
                (59, StatusControl::Map),
                (60, StatusControl::Faith),
                (61, StatusControl::Power(0)),
                (62, StatusControl::Power(1)),
                (63, StatusControl::Power(2)),
                (64, StatusControl::Power(3)),
                (65, StatusControl::Power(4)),
            ] {
                if rising(scan) {
                    open_status_control(control, engine, &mut ui);
                }
            }
        }
        if rising(66) && !ui.modal_active() {
            inputs.push(InputEvent::QuickLoad);
        }
        if rising(67) && !ui.modal_active() {
            inputs.push(InputEvent::QuickSave);
        }
        if rising(82) {
            if ui.choices_active() || ui.study_active() {
                ui.move_selection(-1);
            } else {
                inputs.push(InputEvent::Action(".u".into()));
            }
        }
        if rising(81) {
            if ui.choices_active() || ui.study_active() {
                ui.move_selection(1);
            } else {
                inputs.push(InputEvent::Action(".d".into()));
            }
        }
        if rising(75) && ui.study_active() {
            ui.move_selection(-18);
        }
        if rising(78) && ui.study_active() {
            ui.move_selection(18);
        }
        if rising(80) && !ui.modal_active() {
            inputs.push(InputEvent::Action(".l".into()));
        }
        if rising(79) && !ui.modal_active() {
            inputs.push(InputEvent::Action(".r".into()));
        }
        for scan in 4..=29 {
            if rising(scan) {
                if scan == 4 && ui.study_active() {
                    if let Some(input) = ui.activate() {
                        inputs.push(input);
                    }
                } else if !ui.modal_active() {
                    inputs.push(InputEvent::Key((b'a' + (scan - 4) as u8) as char));
                }
            }
        }
        previous_keys.clear();
        previous_keys.extend_from_slice(keys);

        let (mut window_x, mut window_y) = (0.0f32, 0.0f32);
        let buttons = unsafe { SDL_GetMouseState(&mut window_x, &mut window_y) };
        let (mut logical_x, mut logical_y) = (0.0f32, 0.0f32);
        unsafe {
            SDL_RenderCoordinatesFromWindow(
                sdl.renderer,
                window_x,
                window_y,
                &mut logical_x,
                &mut logical_y,
            );
        }
        let display_x = logical_x.round() as i32;
        let display_y = logical_y.round() as i32;
        if previous_pointer != Some((display_x, display_y)) {
            ui.pointer_move(display_x, display_y);
            previous_pointer = Some((display_x, display_y));
        }
        let x = (display_x / DISPLAY_SCALE as i32).clamp(0, (SCREEN_WIDTH - 1) as i32) as i16;
        let y = (display_y / DISPLAY_SCALE as i32).clamp(0, (SCREEN_HEIGHT - 1) as i32) as i16;
        inputs.push(InputEvent::PointerMove { x, y });
        if buttons & 1 != 0 && previous_buttons & 1 == 0 {
            if let Some(input) = ui.pointer_click(display_x, display_y) {
                inputs.push(input);
            } else if !ui.modal_active() {
                let status = status_bar_state(engine);
                if let Some(control) = status_control_at(display_x, display_y, &ui_assets, status) {
                    open_status_control(control, engine, &mut ui);
                } else {
                    inputs.push(InputEvent::PointerClick { x, y });
                }
            }
        }
        previous_buttons = buttons;

        let now = unsafe { SDL_GetTicks() };
        let elapsed_ms = now.saturating_sub(previous_tick).max(1);
        previous_tick = now;
        let elapsed_units = reference_timer.advance_milliseconds(elapsed_ms);
        engine.tick_elapsed(inputs, elapsed_units)?;
        for event in engine.take_events() {
            match event {
                EngineEvent::SceneChanged { scene, .. } => {
                    ui.clear();
                    eprintln!("scene: {scene}");
                }
                EngineEvent::Dialogue { channel, text } => {
                    ui.show_dialogue(channel, text.clone(), engine.dialogue_presentation(channel));
                    eprintln!("{text}");
                }
                EngineEvent::Choices(choices) => {
                    ui.show_choices(
                        choices.clone(),
                        engine.choice_presentation(),
                        engine.menu_selection(),
                    );
                    for (index, choice) in choices.iter().enumerate() {
                        eprintln!("{}{choice}", if index == 0 { "> " } else { "  " });
                    }
                }
                EngineEvent::StudyRequested { .. } => {
                    let study_records = engine.available_study_records();
                    ui.show_study(study_records.clone());
                    eprintln!("Computer Bible:");
                    for (index, record) in study_records.iter().enumerate() {
                        eprintln!(
                            "{}{} - {}",
                            if index == 0 { "> " } else { "  " },
                            record.citation,
                            record.verse
                        );
                    }
                }
                _ => {}
            }
        }
        sdl.present(engine, &ui, &ui_assets)?;
        unsafe {
            SDL_Delay(16);
        }
    }
}

fn status_bar_state(engine: &Engine) -> StatusBarState {
    StatusBarState {
        visible: engine.status_controls_visible(),
        faith: engine.state.variables[21],
        powers: std::array::from_fn(|index| engine.state.flag(0x30 + index as u8)),
    }
}

fn open_status_control(control: StatusControl, engine: &Engine, ui: &mut UiState) {
    match control {
        StatusControl::Bible => ui.show_study_browser(engine.available_study_records()),
        StatusControl::Map => {
            let explored = std::array::from_fn(|index| engine.state.variables[37 + index] as u16);
            ui.show_map(
                engine.state.world.clone(),
                explored,
                usize::try_from(engine.state.variables[11]).unwrap_or(0),
                usize::try_from(engine.state.variables[12]).unwrap_or(0),
            );
        }
        StatusControl::Faith => {
            let faith = engine.state.variables[21].clamp(0, 10_000);
            let text = if faith == 10_000 {
                "FAITH: 100%".to_owned()
            } else {
                format!("FAITH: {}.{:02}%", faith / 100, faith % 100)
            };
            ui.show_notice(text);
        }
        StatusControl::Power(index) if engine.state.flag(0x30 + index as u8) => {
            let name = ["SWORD", "SHIELD", "NO TRAP", "CANDLE", "FLIGHT"][index];
            ui.show_notice(format!("{name} POWER IS ACTIVE"));
        }
        StatusControl::Power(_) => {}
    }
}

fn sdl_error(operation: &str) -> EngineError {
    let message = unsafe {
        let pointer = SDL_GetError();
        if pointer.is_null() {
            "unknown SDL error".to_owned()
        } else {
            CStr::from_ptr(pointer).to_string_lossy().into_owned()
        }
    };
    EngineError::format(operation, message)
}
