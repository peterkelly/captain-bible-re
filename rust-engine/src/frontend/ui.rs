use crate::archive::Archive;
use crate::engine::{DialogueChannel, InputEvent, StudyRecord};
use crate::error::{EngineError, Result};
use crate::graphics::{Art, ArtFrame};
use crate::world::WorldMap;

pub const DISPLAY_SCALE: usize = 2;
pub const DISPLAY_WIDTH: usize = 640;
pub const DISPLAY_HEIGHT: usize = 400;

const LINE_HEIGHT: i32 = 16;
const FONT_FIRST: u8 = b'!';
const FONT_GLYPH_COUNT: usize = 95;
const FONT_SECOND_ROW: usize = (b'a' - FONT_FIRST) as usize;
const FONT_HEIGHT: usize = 7;

// Indexed by ASCII character minus '!'. These values are copied from the
// executable's DS:3462 proportional-width table. The font pixels themselves
// are STUFF.ART frame 0.
const FONT_WIDTHS: [u8; FONT_GLYPH_COUNT] = [
    1, 3, 5, 5, 5, 1, 1, 2, 2, 5, 3, 2, 3, 1, 3, 4, 3, 3, 3, 3, 4, 4, 3, 4, 4, 1, 2, 3, 3, 3, 4, 4,
    4, 4, 4, 4, 3, 3, 4, 4, 3, 4, 4, 3, 5, 4, 4, 4, 4, 4, 4, 3, 4, 5, 5, 5, 5, 3, 0, 0, 0, 0, 0, 0,
    4, 4, 4, 4, 4, 4, 4, 4, 1, 4, 4, 1, 5, 4, 4, 4, 4, 4, 4, 3, 4, 5, 5, 5, 4, 3, 0, 0, 0, 0, 0,
];

const STYLE_CHOICE: [u8; 3] = [1, 7, 3];
const STYLE_DIALOGUE: [u8; 3] = [1, 37, 4];
const STYLE_ADVERSARY: [u8; 3] = [15, 86, 90];

#[derive(Clone, Debug)]
pub struct UiAssets {
    font: ArtFrame,
    font_offsets: [usize; FONT_GLYPH_COUNT],
    select: ArtFrame,
    continue_label: ArtFrame,
    bible: ArtFrame,
    map: ArtFrame,
    faith: [ArtFrame; 5],
    powers: [ArtFrame; 5],
    save: ArtFrame,
}

impl UiAssets {
    pub fn load(archive: &Archive) -> Result<Self> {
        let art = Art::parse(&archive.read("STUFF.ART")?)?;
        let font = art.frames.first().cloned().ok_or_else(|| {
            EngineError::format("STUFF.ART", "does not contain the font atlas in frame 0")
        })?;
        if (font.width, font.height) != (257, 14) {
            return Err(EngineError::format(
                "STUFF.ART",
                format!(
                    "font atlas is {}x{}, expected 257x14",
                    font.width, font.height
                ),
            ));
        }
        if font.pixels.iter().any(|&value| value > 2) {
            return Err(EngineError::format(
                "STUFF.ART",
                "font atlas uses a source color above 2",
            ));
        }

        let select = required_frame(&art, 28, "SELECT")?;
        let continue_label = required_frame(&art, 29, "CONTINUE")?;
        let bible = required_frame(&art, 4, "Computer Bible")?;
        let map = required_frame(&art, 32, "map")?;
        let faith = [
            required_frame(&art, 22, "full-faith")?,
            required_frame(&art, 23, "high-faith")?,
            required_frame(&art, 24, "medium-faith")?,
            required_frame(&art, 25, "low-faith")?,
            required_frame(&art, 26, "empty-faith")?,
        ];
        let powers = [
            required_frame(&art, 17, "Sword")?,
            required_frame(&art, 18, "Shield")?,
            required_frame(&art, 19, "No Trap")?,
            required_frame(&art, 20, "Candle")?,
            required_frame(&art, 21, "Flight")?,
        ];
        let save = required_frame(&art, 11, "save")?;
        let font_offsets = font_offsets(&font)?;
        Ok(Self {
            font,
            font_offsets,
            select,
            continue_label,
            bible,
            map,
            faith,
            powers,
            save,
        })
    }
}

fn required_frame(art: &Art, index: usize, name: &str) -> Result<ArtFrame> {
    art.frames.get(index).cloned().ok_or_else(|| {
        EngineError::format(
            "STUFF.ART",
            format!("does not contain {name} frame {index}"),
        )
    })
}

fn font_offsets(font: &ArtFrame) -> Result<[usize; FONT_GLYPH_COUNT]> {
    let stride = usize::from(font.width);
    let mut offsets = [0; FONT_GLYPH_COUNT];
    let mut x = 0usize;
    for (index, &width) in FONT_WIDTHS.iter().enumerate() {
        if index == FONT_SECOND_ROW {
            x = 0;
        }
        if width != 0 && x + usize::from(width) > stride {
            return Err(EngineError::format(
                "STUFF.ART",
                format!("font glyph {index} exceeds its atlas row"),
            ));
        }
        offsets[index] = if index < FONT_SECOND_ROW {
            x
        } else {
            stride * FONT_HEIGHT + x
        };
        x += usize::from(width) + 1;
    }
    Ok(offsets)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Rect {
    x: i32,
    y: i32,
    width: i32,
    height: i32,
}

impl Rect {
    fn right(self) -> i32 {
        self.x + self.width
    }

    fn bottom(self) -> i32 {
        self.y + self.height
    }

    fn contains(self, x: i32, y: i32) -> bool {
        x >= self.x && x < self.right() && y >= self.y && y < self.bottom()
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct StatusBarState {
    pub visible: bool,
    pub faith: i16,
    pub powers: [bool; 5],
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StatusControl {
    Bible,
    Map,
    Faith,
    Power(usize),
}

#[derive(Clone, Debug)]
struct DialogueUi {
    channel: DialogueChannel,
    text: String,
    presentation: [u8; 3],
}

#[derive(Clone, Debug)]
struct ChoicesUi {
    choices: Vec<String>,
    presentation: [u8; 3],
    selected: usize,
}

#[derive(Clone, Debug)]
struct StudyUi {
    records: Vec<StudyRecord>,
    selected: usize,
    apply_selection: bool,
}

#[derive(Clone, Debug)]
struct MapUi {
    world: WorldMap,
    explored: [u16; 16],
    current_x: usize,
    current_y: usize,
}

#[derive(Clone, Debug)]
enum ModalUi {
    Dialogue(DialogueUi),
    Choices(ChoicesUi),
    Study(StudyUi),
    Map(Box<MapUi>),
    Notice(DialogueUi),
}

#[derive(Clone, Debug, Default)]
pub struct UiState {
    modal: Option<ModalUi>,
}

impl UiState {
    pub fn show_dialogue(&mut self, channel: DialogueChannel, text: String, presentation: [u8; 3]) {
        self.modal = Some(ModalUi::Dialogue(DialogueUi {
            channel,
            text,
            presentation,
        }));
    }

    pub fn show_choices(&mut self, choices: Vec<String>, presentation: [u8; 3], selected: usize) {
        let selected = selected.min(choices.len().saturating_sub(1));
        self.modal = Some(ModalUi::Choices(ChoicesUi {
            choices,
            presentation,
            selected,
        }));
    }

    pub fn show_study(&mut self, records: Vec<StudyRecord>) {
        self.modal = Some(ModalUi::Study(StudyUi {
            records,
            selected: 0,
            apply_selection: true,
        }));
    }

    pub fn show_study_browser(&mut self, records: Vec<StudyRecord>) {
        self.modal = Some(ModalUi::Study(StudyUi {
            records,
            selected: 0,
            apply_selection: false,
        }));
    }

    pub fn show_map(
        &mut self,
        world: WorldMap,
        explored: [u16; 16],
        current_x: usize,
        current_y: usize,
    ) {
        self.modal = Some(ModalUi::Map(Box::new(MapUi {
            world,
            explored,
            current_x: current_x.min(15),
            current_y: current_y.min(15),
        })));
    }

    pub fn show_notice(&mut self, text: String) {
        self.modal = Some(ModalUi::Notice(DialogueUi {
            channel: DialogueChannel::CaptainBible,
            text,
            presentation: [60, 80, 200],
        }));
    }

    pub fn clear(&mut self) {
        self.modal = None;
    }

    pub fn modal_active(&self) -> bool {
        self.modal.is_some()
    }

    pub fn choices_active(&self) -> bool {
        matches!(self.modal, Some(ModalUi::Choices(_)))
    }

    pub fn study_active(&self) -> bool {
        matches!(self.modal, Some(ModalUi::Study(_)))
    }

    pub fn move_selection(&mut self, amount: isize) {
        match &mut self.modal {
            Some(ModalUi::Choices(menu)) => {
                menu.selected = offset_clamped(menu.selected, amount, menu.choices.len());
            }
            Some(ModalUi::Study(study)) => {
                study.selected = offset_clamped(study.selected, amount, study.records.len());
            }
            _ => {}
        }
    }

    pub fn pointer_move(&mut self, x: i32, y: i32) {
        match &mut self.modal {
            Some(ModalUi::Choices(menu)) => {
                if let Some(index) = choice_at(menu, x, y) {
                    menu.selected = index;
                }
            }
            Some(ModalUi::Study(study)) => {
                if let Some(index) = study_at(study, x, y) {
                    study.selected = index;
                }
            }
            _ => {}
        }
    }

    pub fn activate(&mut self) -> Option<InputEvent> {
        let input = match self.modal.as_ref()? {
            ModalUi::Dialogue(_) => InputEvent::Confirm,
            ModalUi::Choices(menu) if !menu.choices.is_empty() => InputEvent::Choose(menu.selected),
            ModalUi::Study(study) if study.apply_selection => {
                InputEvent::ApplyStudy(study.records.get(study.selected)?.selector)
            }
            ModalUi::Study(_) => return None,
            ModalUi::Map(_) | ModalUi::Notice(_) => InputEvent::Cancel,
            ModalUi::Choices(_) => return None,
        };
        self.clear();
        Some(input)
    }

    pub fn cancel(&mut self) -> Option<InputEvent> {
        let input = match self.modal.as_ref()? {
            ModalUi::Dialogue(_) => InputEvent::Cancel,
            ModalUi::Study(_) => InputEvent::Cancel,
            ModalUi::Map(_) | ModalUi::Notice(_) => InputEvent::Cancel,
            ModalUi::Choices(_) => return None,
        };
        self.clear();
        Some(input)
    }

    pub fn pointer_click(&mut self, x: i32, y: i32) -> Option<InputEvent> {
        let input = match self.modal.as_ref()? {
            ModalUi::Dialogue(_) => InputEvent::Confirm,
            ModalUi::Choices(menu) => InputEvent::Choose(choice_at(menu, x, y)?),
            ModalUi::Study(study) if study.apply_selection => {
                let index = study_at(study, x, y)?;
                InputEvent::ApplyStudy(study.records.get(index)?.selector)
            }
            ModalUi::Study(_) => return None,
            ModalUi::Map(_) | ModalUi::Notice(_) => InputEvent::Cancel,
        };
        self.clear();
        Some(input)
    }

    pub fn draw(&self, pixels: &mut [u32], assets: &UiAssets, colors: &[u32; 256]) {
        debug_assert_eq!(pixels.len(), DISPLAY_WIDTH * DISPLAY_HEIGHT);
        match &self.modal {
            Some(ModalUi::Dialogue(dialogue)) => draw_dialogue(pixels, dialogue, assets, colors),
            Some(ModalUi::Choices(menu)) => draw_choices(pixels, menu, assets, colors),
            Some(ModalUi::Study(study)) => draw_study(pixels, study, assets, colors),
            Some(ModalUi::Map(map)) => draw_map(pixels, map, assets, colors),
            Some(ModalUi::Notice(notice)) => draw_dialogue(pixels, notice, assets, colors),
            None => {}
        }
    }
}

fn offset_clamped(current: usize, amount: isize, count: usize) -> usize {
    if count == 0 {
        return 0;
    }
    current
        .saturating_add_signed(amount)
        .min(count.saturating_sub(1))
}

fn default_presentation(channel: DialogueChannel) -> [u8; 3] {
    match channel {
        DialogueChannel::CaptainBible => [4, 30, 150],
        DialogueChannel::Adversary | DialogueChannel::Character => [162, 89, 150],
    }
}

fn valid_presentation(value: [u8; 3], channel: DialogueChannel) -> [u8; 3] {
    if value[2] < 24 {
        default_presentation(channel)
    } else {
        value
    }
}

#[derive(Clone, Debug)]
struct PanelLayout {
    panel: Rect,
    text_x: i32,
    text_y: i32,
    lines: Vec<String>,
}

fn panel_layout(text: &str, presentation: [u8; 3], channel: DialogueChannel) -> PanelLayout {
    let [x, y, width] = valid_presentation(presentation, channel);
    let text_x = i32::from(x) * DISPLAY_SCALE as i32;
    let text_y = i32::from(y) * DISPLAY_SCALE as i32;
    let logical_text_width = usize::from(width);
    let text_width = i32::from(width) * DISPLAY_SCALE as i32;
    let lines = wrap_text(text, logical_text_width);
    let mut panel = Rect {
        x: text_x - 6,
        y: text_y - 10,
        width: text_width + 12,
        height: lines.len() as i32 * LINE_HEIGHT + 16,
    };
    if panel.right() > DISPLAY_WIDTH as i32 {
        panel.x -= panel.right() - DISPLAY_WIDTH as i32;
    }
    if panel.bottom() > DISPLAY_HEIGHT as i32 {
        panel.y -= panel.bottom() - DISPLAY_HEIGHT as i32;
    }
    panel.x = panel.x.max(0);
    panel.y = panel.y.max(0);
    PanelLayout {
        text_x: panel.x + 6,
        text_y: panel.y + 10,
        panel,
        lines,
    }
}

fn draw_dialogue(
    pixels: &mut [u32],
    dialogue: &DialogueUi,
    assets: &UiAssets,
    colors: &[u32; 256],
) {
    let layout = panel_layout(&dialogue.text, dialogue.presentation, dialogue.channel);
    draw_panel(pixels, layout.panel, colors);
    let style = if dialogue.channel == DialogueChannel::Adversary {
        STYLE_ADVERSARY
    } else {
        STYLE_DIALOGUE
    };
    for (index, line) in layout.lines.iter().enumerate() {
        draw_text(
            pixels,
            layout.text_x,
            layout.text_y + index as i32 * LINE_HEIGHT,
            line,
            assets,
            style,
            colors,
        );
    }
    draw_art_frame(
        pixels,
        &assets.continue_label,
        layout.panel.x + layout.panel.width / 2,
        layout.panel.y,
        colors,
    );
}

fn choices_layout(menu: &ChoicesUi) -> (Rect, i32, i32, Vec<Vec<String>>, Vec<Rect>) {
    let presentation = valid_presentation(menu.presentation, DialogueChannel::CaptainBible);
    let text_x = i32::from(presentation[0]) * DISPLAY_SCALE as i32;
    let text_y = i32::from(presentation[1]) * DISPLAY_SCALE as i32;
    let logical_text_width = usize::from(presentation[2]);
    let text_width = i32::from(presentation[2]) * DISPLAY_SCALE as i32;
    let wrapped: Vec<_> = menu
        .choices
        .iter()
        .map(|choice| wrap_text(choice, logical_text_width))
        .collect();
    let total_lines: usize = wrapped.iter().map(Vec::len).sum();
    let mut panel = Rect {
        x: text_x - 6,
        y: text_y - 10,
        width: text_width + 12,
        height: total_lines as i32 * LINE_HEIGHT + 16,
    };
    if panel.bottom() > DISPLAY_HEIGHT as i32 {
        panel.y -= panel.bottom() - DISPLAY_HEIGHT as i32;
    }
    panel.x = panel.x.max(0);
    panel.y = panel.y.max(0);
    let text_x = panel.x + 6;
    let text_y = panel.y + 10;
    let mut line = 0i32;
    let rows = wrapped
        .iter()
        .map(|choice| {
            let row = Rect {
                x: panel.x,
                y: text_y + line * LINE_HEIGHT,
                width: (panel.width + 96).min(DISPLAY_WIDTH as i32 - panel.x),
                height: choice.len() as i32 * LINE_HEIGHT,
            };
            line += choice.len() as i32;
            row
        })
        .collect();
    (panel, text_x, text_y, wrapped, rows)
}

fn choice_at(menu: &ChoicesUi, x: i32, y: i32) -> Option<usize> {
    let (_, _, _, _, rows) = choices_layout(menu);
    rows.iter().position(|row| row.contains(x, y))
}

fn draw_choices(pixels: &mut [u32], menu: &ChoicesUi, assets: &UiAssets, colors: &[u32; 256]) {
    let (panel, text_x, text_y, wrapped, rows) = choices_layout(menu);
    draw_panel(pixels, panel, colors);
    let mut line = 0i32;
    for (choice_index, choice) in wrapped.iter().enumerate() {
        let style = if choice_index == menu.selected {
            STYLE_DIALOGUE
        } else {
            STYLE_CHOICE
        };
        for value in choice {
            draw_text(
                pixels,
                text_x,
                text_y + line * LINE_HEIGHT,
                value,
                assets,
                style,
                colors,
            );
            line += 1;
        }
    }
    if let Some(row) = rows.get(menu.selected) {
        let anchor_x = panel.right() - 6 - i32::from(assets.select.origin_x) * 2;
        draw_art_frame(pixels, &assets.select, anchor_x, row.y, colors);
    }
}

pub fn draw_scene_overlays(
    pixels: &mut [u32],
    assets: &UiAssets,
    colors: &[u32; 256],
    status: StatusBarState,
) {
    draw_art_frame(pixels, &assets.save, 0, 0, colors);
    if !status.visible {
        return;
    }
    draw_art_frame(pixels, &assets.bible, 0, 0, colors);
    draw_art_frame(pixels, &assets.map, 0, 0, colors);
    let faith = status.faith.clamp(0, 10_000) as usize;
    let faith_frame = ((10_000 - faith) * 5 / 10_001).min(4);
    draw_art_frame(pixels, &assets.faith[faith_frame], 0, 0, colors);
    for (enabled, frame) in status.powers.into_iter().zip(&assets.powers) {
        if enabled {
            draw_art_frame(pixels, frame, 0, 0, colors);
        }
    }
}

pub fn status_control_at(
    x: i32,
    y: i32,
    assets: &UiAssets,
    status: StatusBarState,
) -> Option<StatusControl> {
    if !status.visible {
        return None;
    }
    for (control, frame) in [
        (StatusControl::Bible, &assets.bible),
        (StatusControl::Map, &assets.map),
        (StatusControl::Faith, &assets.faith[0]),
    ] {
        if art_rect(frame, 0, 0).contains(x, y) {
            return Some(control);
        }
    }
    status
        .powers
        .into_iter()
        .zip(&assets.powers)
        .enumerate()
        .find_map(|(index, (enabled, frame))| {
            (enabled && art_rect(frame, 0, 0).contains(x, y)).then_some(StatusControl::Power(index))
        })
}

fn art_rect(frame: &ArtFrame, anchor_x: i32, anchor_y: i32) -> Rect {
    Rect {
        x: anchor_x + i32::from(frame.origin_x) * DISPLAY_SCALE as i32,
        y: anchor_y + i32::from(frame.origin_y) * DISPLAY_SCALE as i32,
        width: i32::from(frame.width) * DISPLAY_SCALE as i32,
        height: i32::from(frame.height) * DISPLAY_SCALE as i32,
    }
}

const STUDY_PANEL: Rect = Rect {
    x: 12,
    y: 20,
    width: 616,
    height: 360,
};
const STUDY_LIST_X: i32 = 24;
const STUDY_LIST_Y: i32 = 58;
const STUDY_ROWS: usize = 18;

fn visible_study_range(study: &StudyUi) -> std::ops::Range<usize> {
    let first = study
        .selected
        .saturating_sub(STUDY_ROWS.saturating_sub(1))
        .min(study.records.len().saturating_sub(STUDY_ROWS));
    first..(first + STUDY_ROWS).min(study.records.len())
}

fn study_at(study: &StudyUi, x: i32, y: i32) -> Option<usize> {
    let list = Rect {
        x: STUDY_LIST_X - 4,
        y: STUDY_LIST_Y,
        width: 190,
        height: STUDY_ROWS as i32 * LINE_HEIGHT,
    };
    if !list.contains(x, y) {
        return None;
    }
    let range = visible_study_range(study);
    let row = ((y - STUDY_LIST_Y) / LINE_HEIGHT) as usize;
    let index = range.start + row;
    (index < range.end).then_some(index)
}

fn draw_study(pixels: &mut [u32], study: &StudyUi, assets: &UiAssets, colors: &[u32; 256]) {
    draw_panel(pixels, STUDY_PANEL, colors);
    draw_text(
        pixels,
        24,
        30,
        "COMPUTER BIBLE",
        assets,
        STYLE_DIALOGUE,
        colors,
    );
    draw_text(
        pixels,
        458,
        354,
        "ENTER: APPLY",
        assets,
        STYLE_DIALOGUE,
        colors,
    );
    draw_text(pixels, 24, 354, "ESC: OFF", assets, STYLE_DIALOGUE, colors);

    let range = visible_study_range(study);
    for (row, index) in range.clone().enumerate() {
        let style = if index == study.selected {
            STYLE_DIALOGUE
        } else {
            STYLE_CHOICE
        };
        let citation = truncate_chars(&study.records[index].citation, 22);
        draw_text(
            pixels,
            STUDY_LIST_X,
            STUDY_LIST_Y + row as i32 * LINE_HEIGHT,
            &citation,
            assets,
            style,
            colors,
        );
    }

    if let Some(record) = study.records.get(study.selected) {
        draw_text(
            pixels,
            222,
            58,
            &record.citation,
            assets,
            STYLE_DIALOGUE,
            colors,
        );
        for (line, value) in wrap_text(&record.verse, 192).iter().enumerate() {
            draw_text(
                pixels,
                222,
                82 + line as i32 * LINE_HEIGHT,
                value,
                assets,
                STYLE_CHOICE,
                colors,
            );
        }
    } else {
        draw_text(
            pixels,
            24,
            58,
            "NO OBTAINED VERSES",
            assets,
            STYLE_CHOICE,
            colors,
        );
    }
}

const MAP_PANEL: Rect = Rect {
    x: 160,
    y: 24,
    width: 320,
    height: 352,
};
const MAP_LEFT: i32 = 208;
const MAP_TOP: i32 = 70;
const MAP_CELL: i32 = 14;

fn draw_map(pixels: &mut [u32], map: &MapUi, assets: &UiAssets, colors: &[u32; 256]) {
    draw_panel(pixels, MAP_PANEL, colors);
    draw_text(pixels, 292, 38, "MAP", assets, STYLE_DIALOGUE, colors);
    draw_text(pixels, 180, 350, "ESC: OFF", assets, STYLE_DIALOGUE, colors);

    for y in 0..16 {
        for x in 0..16 {
            let cell = map.world.cell(x, y).expect("fixed map coordinates");
            if cell.packed == 0 {
                continue;
            }
            let explored = map.explored[y] & (1u16 << x) != 0;
            let color = if explored { colors[31] } else { colors[7] };
            let left = MAP_LEFT + x as i32 * MAP_CELL;
            let top = MAP_TOP + y as i32 * MAP_CELL;
            let center_x = left + MAP_CELL / 2;
            let center_y = top + MAP_CELL / 2;
            fill_rect(
                pixels,
                Rect {
                    x: center_x - 2,
                    y: center_y - 2,
                    width: 4,
                    height: 4,
                },
                color,
            );
            for (mask, rect) in [
                (
                    0x10,
                    Rect {
                        x: center_x - 1,
                        y: top,
                        width: 2,
                        height: MAP_CELL / 2,
                    },
                ),
                (
                    0x20,
                    Rect {
                        x: center_x - 1,
                        y: center_y,
                        width: 2,
                        height: MAP_CELL / 2,
                    },
                ),
                (
                    0x40,
                    Rect {
                        x: left,
                        y: center_y - 1,
                        width: MAP_CELL / 2,
                        height: 2,
                    },
                ),
                (
                    0x80,
                    Rect {
                        x: center_x,
                        y: center_y - 1,
                        width: MAP_CELL / 2,
                        height: 2,
                    },
                ),
            ] {
                if cell.connections() & mask != 0 {
                    fill_rect(pixels, rect, color);
                }
            }
        }
    }

    fill_rect(
        pixels,
        Rect {
            x: MAP_LEFT + map.current_x as i32 * MAP_CELL + 3,
            y: MAP_TOP + map.current_y as i32 * MAP_CELL + 3,
            width: 8,
            height: 8,
        },
        colors[37],
    );
}

fn truncate_chars(value: &str, count: usize) -> String {
    value.chars().take(count).collect()
}

fn wrap_text(value: &str, logical_width: usize) -> Vec<String> {
    let logical_width = logical_width.max(1);
    let mut result = Vec::new();
    for paragraph in value.split('\n') {
        let mut remaining = paragraph.trim_end().to_owned();
        if remaining.is_empty() {
            result.push(String::new());
            continue;
        }
        while text_width(&remaining) > logical_width {
            let mut line_width = 0usize;
            let mut last_space = None;
            let mut overflow = None;
            for (offset, character) in remaining.char_indices() {
                if character.is_whitespace() && offset != 0 {
                    last_space = Some(offset);
                }
                if line_width + character_advance(character) > logical_width {
                    overflow = Some(offset);
                    break;
                }
                line_width += character_advance(character);
            }
            let overflow = overflow.unwrap_or(remaining.len());
            let split = last_space
                .filter(|&offset| offset <= overflow)
                .unwrap_or_else(|| {
                    if overflow == 0 {
                        remaining
                            .char_indices()
                            .nth(1)
                            .map(|(offset, _)| offset)
                            .unwrap_or(remaining.len())
                    } else {
                        overflow
                    }
                });
            let (line, rest) = remaining.split_at(split);
            result.push(line.trim_end().to_owned());
            remaining = rest.trim_start().to_owned();
        }
        result.push(remaining);
    }
    result
}

fn draw_panel(pixels: &mut [u32], panel: Rect, colors: &[u32; 256]) {
    fill_rect(
        pixels,
        Rect {
            x: panel.x + 4,
            y: panel.y + 4,
            ..panel
        },
        colors[0],
    );
    fill_rect(pixels, panel, colors[37]);
    fill_rect(
        pixels,
        Rect {
            x: panel.x + 2,
            y: panel.y + 2,
            width: panel.width - 4,
            height: panel.height - 4,
        },
        colors[4],
    );
    fill_rect(
        pixels,
        Rect {
            x: panel.x + 4,
            y: panel.y + 4,
            width: panel.width - 8,
            height: panel.height - 8,
        },
        colors[1],
    );
}

fn fill_rect(pixels: &mut [u32], rect: Rect, color: u32) {
    let left = rect.x.clamp(0, DISPLAY_WIDTH as i32);
    let right = rect.right().clamp(0, DISPLAY_WIDTH as i32);
    let top = rect.y.clamp(0, DISPLAY_HEIGHT as i32);
    let bottom = rect.bottom().clamp(0, DISPLAY_HEIGHT as i32);
    for y in top..bottom {
        let row = y as usize * DISPLAY_WIDTH;
        pixels[row + left as usize..row + right as usize].fill(color);
    }
}

fn draw_text(
    pixels: &mut [u32],
    mut x: i32,
    y: i32,
    text: &str,
    assets: &UiAssets,
    style: [u8; 3],
    colors: &[u32; 256],
) {
    for character in text.chars() {
        let ascii = font_character(character);
        if ascii > b' ' {
            let index = usize::from(ascii - FONT_FIRST);
            draw_glyph(pixels, x, y, index, assets, style, colors);
        }
        x += character_advance(character) as i32 * DISPLAY_SCALE as i32;
    }
}

fn draw_glyph(
    pixels: &mut [u32],
    x: i32,
    y: i32,
    index: usize,
    assets: &UiAssets,
    style: [u8; 3],
    colors: &[u32; 256],
) {
    let width = usize::from(FONT_WIDTHS[index]);
    let stride = usize::from(assets.font.width);
    let offset = assets.font_offsets[index];
    for row in 0..FONT_HEIGHT {
        for column in 0..width {
            let source = usize::from(assets.font.pixels[offset + row * stride + column]);
            draw_scaled_pixel(
                pixels,
                x + (column * DISPLAY_SCALE) as i32,
                y + (row * DISPLAY_SCALE) as i32,
                colors[usize::from(style[source])],
            );
        }
    }
}

fn draw_art_frame(
    pixels: &mut [u32],
    frame: &ArtFrame,
    anchor_x: i32,
    anchor_y: i32,
    colors: &[u32; 256],
) {
    let left = anchor_x + i32::from(frame.origin_x) * DISPLAY_SCALE as i32;
    let top = anchor_y + i32::from(frame.origin_y) * DISPLAY_SCALE as i32;
    let stride = usize::from(frame.width);
    for source_y in 0..usize::from(frame.height) {
        for source_x in 0..stride {
            let index = frame.pixels[source_y * stride + source_x];
            if index != 0 {
                draw_scaled_pixel(
                    pixels,
                    left + (source_x * DISPLAY_SCALE) as i32,
                    top + (source_y * DISPLAY_SCALE) as i32,
                    colors[usize::from(index)],
                );
            }
        }
    }
}

fn draw_scaled_pixel(pixels: &mut [u32], x: i32, y: i32, color: u32) {
    for offset_y in 0..DISPLAY_SCALE as i32 {
        let pixel_y = y + offset_y;
        if !(0..DISPLAY_HEIGHT as i32).contains(&pixel_y) {
            continue;
        }
        for offset_x in 0..DISPLAY_SCALE as i32 {
            let pixel_x = x + offset_x;
            if (0..DISPLAY_WIDTH as i32).contains(&pixel_x) {
                pixels[pixel_y as usize * DISPLAY_WIDTH + pixel_x as usize] = color;
            }
        }
    }
}

fn text_width(text: &str) -> usize {
    text.chars().map(character_advance).sum()
}

fn character_advance(character: char) -> usize {
    let ascii = font_character(character);
    if ascii <= b' ' {
        3
    } else {
        usize::from(FONT_WIDTHS[usize::from(ascii - FONT_FIRST)]) + 1
    }
}

fn font_character(character: char) -> u8 {
    match character {
        'À' | 'Á' | 'Â' | 'Ã' | 'Ä' | 'Å' => b'A',
        'Ç' => b'C',
        'È' | 'É' | 'Ê' | 'Ë' => b'E',
        'Ì' | 'Í' | 'Î' | 'Ï' => b'I',
        'Ñ' => b'N',
        'Ò' | 'Ó' | 'Ô' | 'Õ' | 'Ö' => b'O',
        'Ù' | 'Ú' | 'Û' | 'Ü' => b'U',
        'Ý' | 'Ÿ' => b'Y',
        'à' | 'á' | 'â' | 'ã' | 'ä' | 'å' => b'a',
        'ç' => b'c',
        'è' | 'é' | 'ê' | 'ë' => b'e',
        'ì' | 'í' | 'î' | 'ï' => b'i',
        'ñ' => b'n',
        'ò' | 'ó' | 'ô' | 'õ' | 'ö' => b'o',
        'ù' | 'ú' | 'û' | 'ü' => b'u',
        'ý' | 'ÿ' => b'y',
        '¿' => b'?',
        '¡' => b'!',
        ' '..='\u{7f}' => character as u8,
        _ => b'?',
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn frame(origin_x: i16, origin_y: i16, width: u16, height: u16, color: u8) -> ArtFrame {
        ArtFrame {
            origin_x,
            origin_y,
            width,
            height,
            pixels: vec![color; usize::from(width) * usize::from(height)],
        }
    }

    fn assets() -> UiAssets {
        let font = frame(11, 7, 257, 14, 1);
        UiAssets {
            font_offsets: font_offsets(&font).unwrap(),
            font,
            select: frame(-12, -3, 24, 7, 28),
            continue_label: frame(-17, -3, 35, 7, 29),
            bible: frame(4, 1, 16, 16, 4),
            map: frame(23, 1, 16, 16, 32),
            faith: std::array::from_fn(|index| frame(44, 3, 28, 12, 22 + index as u8)),
            powers: [
                frame(71, 1, 20, 20, 17),
                frame(95, 1, 18, 20, 18),
                frame(118, 1, 26, 21, 19),
                frame(149, 1, 6, 20, 20),
                frame(167, 2, 27, 19, 21),
            ],
            save: frame(297, 1, 20, 17, 11),
        }
    }

    fn colors() -> [u32; 256] {
        std::array::from_fn(|index| 0xff00_0000 | index as u32)
    }

    #[test]
    fn shipped_stuff_art_supplies_the_font_and_action_labels() {
        let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../CB/DD1.DAT");
        if !path.is_file() {
            return;
        }
        let archive = Archive::open(path).unwrap();
        let assets = UiAssets::load(&archive).unwrap();
        assert_eq!((assets.font.width, assets.font.height), (257, 14));
        assert_eq!(
            (
                assets.continue_label.origin_x,
                assets.continue_label.origin_y,
                assets.continue_label.width,
                assets.continue_label.height,
            ),
            (-17, -3, 35, 7)
        );
        assert_eq!(
            (
                assets.select.origin_x,
                assets.select.origin_y,
                assets.select.width,
                assets.select.height,
            ),
            (-12, -3, 24, 7)
        );
        assert_eq!(
            (
                assets.bible.origin_x,
                assets.bible.origin_y,
                assets.bible.width,
                assets.bible.height,
            ),
            (4, 1, 16, 16)
        );
        assert_eq!(
            (
                assets.map.origin_x,
                assets.map.origin_y,
                assets.map.width,
                assets.map.height,
            ),
            (23, 1, 16, 16)
        );
    }

    fn choices() -> ChoicesUi {
        ChoicesUi {
            choices: vec![
                "First response".into(),
                "A second response which wraps onto another line".into(),
                "Final response".into(),
            ],
            presentation: [4, 30, 150],
            selected: 0,
        }
    }

    #[test]
    fn wrapping_uses_the_last_space_and_preserves_text_order() {
        let width = text_width("one two");
        assert_eq!(
            wrap_text("one two three four", width),
            ["one two", "three", "four"]
        );
        assert_eq!(wrap_text("abcdefgh", text_width("abcd")), ["abcd", "efgh"]);
    }

    #[test]
    fn text_measurement_uses_the_dos_proportional_widths() {
        assert!(text_width("iii") < text_width("MMM"));
        assert_eq!(character_advance(' '), 3);
    }

    #[test]
    fn atlas_rows_and_scaled_pixels_match_the_dos_font_model() {
        let assets = assets();
        assert_eq!(assets.font_offsets[FONT_SECOND_ROW], 257 * FONT_HEIGHT);

        let colors = colors();
        let mut pixels = vec![0; DISPLAY_WIDTH * DISPLAY_HEIGHT];
        draw_text(&mut pixels, 20, 30, "!", &assets, STYLE_DIALOGUE, &colors);
        for y in 30..32 {
            for x in 20..22 {
                assert_eq!(pixels[y * DISPLAY_WIDTH + x], colors[37]);
            }
        }
        assert_eq!(pixels[30 * DISPLAY_WIDTH + 22], 0);
    }

    #[test]
    fn continue_art_uses_its_signed_anchor() {
        let assets = assets();
        let colors = colors();
        let mut pixels = vec![0; DISPLAY_WIDTH * DISPLAY_HEIGHT];
        draw_art_frame(&mut pixels, &assets.continue_label, 100, 40, &colors);
        assert_eq!(pixels[34 * DISPLAY_WIDTH + 66], colors[29]);
        assert_eq!(pixels[33 * DISPLAY_WIDTH + 66], 0);
    }

    #[test]
    fn status_bar_draws_and_hits_the_original_artwork_bounds() {
        let assets = assets();
        let colors = colors();
        let status = StatusBarState {
            visible: true,
            faith: 10_000,
            powers: [false; 5],
        };
        let mut pixels = vec![0; DISPLAY_WIDTH * DISPLAY_HEIGHT];
        draw_scene_overlays(&mut pixels, &assets, &colors, status);

        assert_eq!(pixels[2 * DISPLAY_WIDTH + 8], colors[4]);
        assert_eq!(pixels[2 * DISPLAY_WIDTH + 46], colors[32]);
        assert_eq!(pixels[6 * DISPLAY_WIDTH + 88], colors[22]);
        assert_eq!(pixels[2 * DISPLAY_WIDTH + 594], colors[11]);
        assert_eq!(
            status_control_at(8, 2, &assets, status),
            Some(StatusControl::Bible)
        );
        assert_eq!(
            status_control_at(46, 2, &assets, status),
            Some(StatusControl::Map)
        );
        assert_eq!(
            status_control_at(88, 6, &assets, status),
            Some(StatusControl::Faith)
        );
    }

    #[test]
    fn standalone_bible_browsing_does_not_apply_an_encounter_answer() {
        let mut ui = UiState::default();
        ui.show_study_browser(vec![StudyRecord {
            selector: 7,
            citation: "Test 1:1".into(),
            verse: "A test verse".into(),
        }]);
        assert_eq!(ui.pointer_click(STUDY_LIST_X, STUDY_LIST_Y), None);
        assert!(ui.study_active());
        assert_eq!(ui.activate(), None);
        assert_eq!(ui.cancel(), Some(InputEvent::Cancel));
        assert!(!ui.modal_active());
    }

    #[test]
    fn selected_choice_art_overlaps_the_panel_like_the_dos_capture() {
        let menu = choices();
        let (panel, _, _, _, rows) = choices_layout(&menu);
        let assets = assets();
        let colors = colors();
        let mut pixels = vec![0; DISPLAY_WIDTH * DISPLAY_HEIGHT];
        draw_choices(&mut pixels, &menu, &assets, &colors);
        let left = panel.right() - 6;
        let top = rows[0].y + i32::from(assets.select.origin_y) * 2;
        assert_eq!(
            pixels[top as usize * DISPLAY_WIDTH + left as usize],
            colors[28]
        );
    }

    #[test]
    fn keyboard_selection_clamps_like_the_dos_menu() {
        let mut ui = UiState::default();
        ui.show_choices(vec!["one".into(), "two".into()], [4, 30, 150], 0);
        ui.move_selection(-1);
        assert_eq!(ui.activate(), Some(InputEvent::Choose(0)));

        ui.show_choices(vec!["one".into(), "two".into()], [4, 30, 150], 0);
        ui.move_selection(8);
        assert_eq!(ui.activate(), Some(InputEvent::Choose(1)));
    }

    #[test]
    fn pointer_hover_and_click_use_wrapped_choice_rows() {
        let mut ui = UiState {
            modal: Some(ModalUi::Choices(choices())),
        };
        let menu = match ui.modal.as_ref().unwrap() {
            ModalUi::Choices(menu) => menu,
            _ => unreachable!(),
        };
        let (_, _, _, _, rows) = choices_layout(menu);
        let third = rows[2];
        ui.pointer_move(third.x + 2, third.y + 2);
        assert_eq!(
            ui.pointer_click(third.x + 2, third.y + 2),
            Some(InputEvent::Choose(2))
        );
    }

    #[test]
    fn select_tag_is_part_of_the_choice_hit_region() {
        let mut ui = UiState {
            modal: Some(ModalUi::Choices(choices())),
        };
        let menu = match ui.modal.as_ref().unwrap() {
            ModalUi::Choices(menu) => menu,
            _ => unreachable!(),
        };
        let (panel, _, _, _, rows) = choices_layout(menu);
        let second = rows[1];
        assert_eq!(
            ui.pointer_click(panel.right() + 8, second.y + 2),
            Some(InputEvent::Choose(1))
        );
    }

    #[test]
    fn clicking_outside_a_choice_panel_does_not_activate_it() {
        let mut ui = UiState {
            modal: Some(ModalUi::Choices(choices())),
        };
        assert_eq!(ui.pointer_click(639, 399), None);
        assert!(ui.choices_active());
    }

    #[test]
    fn dialogue_panel_draws_over_the_scaled_scene() {
        let mut ui = UiState::default();
        ui.show_dialogue(
            DialogueChannel::Character,
            "Visible dialogue".into(),
            [162, 89, 150],
        );
        let mut pixels = vec![0; DISPLAY_WIDTH * DISPLAY_HEIGHT];
        let assets = assets();
        let colors = colors();
        ui.draw(&mut pixels, &assets, &colors);
        assert!(pixels.contains(&colors[1]));
        assert!(pixels.contains(&colors[37]));
    }
}
