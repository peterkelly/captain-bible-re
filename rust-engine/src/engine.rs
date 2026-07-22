//! Resource-driven scene engine and cooperative virtual machine.

use crate::archive::Archive;
use crate::audio::Effect;
use crate::bytecode::{Instruction, Operand, decode, string_operand};
use crate::config::{InstallationPolicy, LaunchConfig, translation_letter};
use crate::error::{EngineError, Result};
use crate::graphics::{Art, Framebuffer, Palette};
use crate::save::{SaveImage, SaveIndex, atomic_write};
use crate::state::GameState;
use crate::text::TextBank;
use crate::world::{MAP_HEIGHT, MAP_WIDTH, WorldMap};
use std::collections::{HashMap, VecDeque};
use std::fs;
use std::path::PathBuf;

const THREAD_COUNT: usize = 10;
const INSTRUCTION_BUDGET: usize = 20_000;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum InputEvent {
    Confirm,
    Cancel,
    Choose(usize),
    ApplyStudy(u8),
    Action(String),
    PointerMove { x: i16, y: i16 },
    PointerClick { x: i16, y: i16 },
    Key(char),
    QuickSave,
    QuickLoad,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum EngineEvent {
    SceneChanged {
        scene: String,
        entry: String,
    },
    Dialogue {
        channel: DialogueChannel,
        text: String,
    },
    Choices(Vec<String>),
    StudyRequested {
        expected_selector: Option<u8>,
        prompt_component: u8,
    },
    Music(u8),
    Sound(u8),
    RestoreRequested,
    ExitRequested,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DialogueChannel {
    Adversary,
    Character,
    CaptainBible,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EngineStatus {
    Running,
    AwaitingInput,
    SceneTransition,
    Exited,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StudyRecord {
    pub selector: u8,
    pub citation: String,
    pub verse: String,
}

#[derive(Clone, Debug, Default)]
struct Thread {
    ip: usize,
    active: bool,
    suspended: bool,
    delay: i16,
    motion_state: u8,
    calls: Vec<usize>,
}

#[derive(Clone, Debug)]
struct SceneActor {
    x: i16,
    y: i16,
    scale: u16,
    frame: u8,
    art_slot: u8,
    flags: u8,
    node: u8,
    previous_node: u8,
    direction: u8,
    animation_phase: u16,
    action_enabled: bool,
    selector: String,
    selector_x: i16,
    selector_y: i16,
}

#[derive(Clone, Copy, Debug)]
struct NavigationNode {
    x: i16,
    y: i16,
    scale: u16,
}

impl Default for SceneActor {
    fn default() -> Self {
        Self {
            x: 0,
            y: 0,
            scale: 0x100,
            frame: 0,
            art_slot: 0,
            flags: 0,
            node: 0,
            previous_node: 0,
            direction: 0,
            animation_phase: 0,
            action_enabled: false,
            selector: String::new(),
            selector_x: 0,
            selector_y: 0,
        }
    }
}

#[derive(Clone, Debug)]
struct AnimationStep {
    frame: u8,
    art_slot: u8,
    x: i16,
    y: i16,
    scale: u16,
    flags: u8,
}

impl AnimationStep {
    fn parse(record: [u8; 9]) -> Self {
        Self {
            frame: record[0],
            art_slot: record[1],
            x: i16::from_le_bytes([record[2], record[3]]),
            y: i16::from_le_bytes([record[4], record[5]]),
            scale: u16::from_le_bytes([record[6], record[7]]),
            flags: record[8],
        }
    }
}

#[derive(Clone, Debug)]
struct Animation {
    interval: i16,
    steps: Vec<AnimationStep>,
    current: usize,
    countdown: i16,
    state: u8,
    linked: Option<usize>,
}

impl Animation {
    fn new(interval: u16) -> Self {
        Self {
            interval: interval as i16,
            steps: Vec::new(),
            current: 0,
            countdown: 0,
            state: 0,
            linked: None,
        }
    }

    fn start(&mut self, state: u8, linked: Option<usize>) -> Result<()> {
        if !(1..=10).contains(&state) {
            return Err(EngineError::format(
                "animation",
                format!("invalid state {state}"),
            ));
        }
        self.state = state;
        self.linked = linked;
        self.current = if matches!(state, 2 | 4 | 6 | 8 | 10) {
            self.steps.len().saturating_sub(1)
        } else {
            0
        };
        self.countdown = self.interval.wrapping_neg();
        Ok(())
    }

    fn finished(&self) -> bool {
        matches!(self.state, 0 | 5 | 6)
    }

    fn advance(&mut self) {
        if self.state == 0 || self.steps.is_empty() {
            return;
        }
        self.countdown = self.countdown.wrapping_add(1);
        if self.countdown <= 0 {
            return;
        }
        self.countdown = self.countdown.wrapping_sub(self.interval);
        let forward = matches!(self.state, 1 | 3 | 7 | 9);
        let backward = matches!(self.state, 2 | 4 | 8 | 10);
        if forward {
            self.current += 1;
        } else if backward {
            self.current = self.current.wrapping_sub(1);
        } else {
            return;
        }
        let outside = self.current >= self.steps.len();
        if !outside {
            return;
        }
        match self.state {
            1 | 2 => {
                self.state = 0;
                self.current = self.current.min(self.steps.len() - 1);
            }
            3 => self.current = 0,
            4 => self.current = self.steps.len() - 1,
            7 => {
                self.current = self.steps.len().saturating_sub(2);
                self.state = 8;
            }
            8 => {
                self.current = usize::from(self.steps.len() > 1);
                self.state = 7;
            }
            9 => {
                self.current = self.steps.len() - 1;
                self.state = 6;
            }
            10 => {
                self.current = 0;
                self.state = 5;
            }
            _ => {}
        }
    }
}

#[derive(Clone, Debug)]
enum DisplaySource {
    Direct {
        frame: u8,
        art_slot: u8,
        x: i16,
        y: i16,
        scale: u16,
        flags: u8,
    },
    Actor(usize),
    Animation(usize),
}

#[derive(Clone, Debug)]
struct DisplayObject {
    source: DisplaySource,
    hidden: bool,
}

#[derive(Clone, Debug)]
struct ActionTarget {
    target: usize,
    x: i16,
    y: i16,
    label: String,
    active: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Selection {
    Actor(usize),
    Action(usize),
}

#[derive(Clone, Debug)]
struct Choice {
    target: usize,
    text: String,
}

#[derive(Clone, Debug)]
struct Callback {
    selector: u8,
    target: usize,
    thread: Option<usize>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum EdgeCallbackPhase {
    ForwardDeparture,
    ReverseDeparture,
    ForwardArrival,
    ReverseArrival,
}

#[derive(Clone, Debug)]
struct EdgeCallback {
    edge: u8,
    phase: EdgeCallbackPhase,
    target: usize,
    thread: Option<usize>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct RouteEdge {
    index: usize,
    from: u8,
    to: u8,
}

#[derive(Clone, Debug)]
struct Movement {
    route: Vec<RouteEdge>,
    current: usize,
    elapsed_units: u32,
    completed_steps: u32,
    duration_steps: u32,
    start_x: i16,
    start_y: i16,
    start_scale: u16,
    end_x: i16,
    end_y: i16,
    end_scale: u16,
}

#[derive(Clone, Debug)]
enum Modal {
    Dialogue { owner: usize },
    Choices { owner: usize },
    Study { owner: usize },
}

#[derive(Clone, Debug)]
struct Scene {
    name: String,
    program: Vec<u8>,
    threads: [Thread; THREAD_COUNT],
    actors: Vec<SceneActor>,
    navigation_nodes: Vec<Option<NavigationNode>>,
    animations: Vec<Animation>,
    art: Vec<Art>,
    display: Vec<DisplayObject>,
    actions: Vec<ActionTarget>,
    choices: Vec<Choice>,
    navigation_edges: Vec<(u8, u8)>,
    entries: Vec<(u8, u8, String)>,
    arrivals: Vec<Callback>,
    departures: Vec<Callback>,
    edge_callbacks: Vec<EdgeCallback>,
    movement: Option<Movement>,
    base_palette: Palette,
    palette: Palette,
    palette_mapping: [u8; 256],
    palette_adjustments: [i16; 256],
    clear_color: u8,
    modal: Option<Modal>,
    action_selection: bool,
    selected_record: Option<u8>,
    study_expected: Option<u8>,
    study_component: u8,
    study_navigation: Option<(u8, u8)>,
    study_success: Option<(u8, usize, usize)>,
    menu_selection: u8,
    captain_presentation: [u8; 3],
    character_presentation: [u8; 3],
    mouse_x: i16,
    mouse_y: i16,
    confirm_latch: bool,
    overlay_active: bool,
    deferred_target: Option<usize>,
    entry_dispatched: bool,
}

impl Scene {
    fn new(name: String, program: Vec<u8>) -> Self {
        let mut threads = std::array::from_fn(|_| Thread::default());
        threads[0].active = true;
        Self {
            name,
            program,
            threads,
            actors: Vec::new(),
            navigation_nodes: Vec::new(),
            animations: Vec::new(),
            art: Vec::new(),
            display: Vec::new(),
            actions: Vec::new(),
            choices: Vec::new(),
            navigation_edges: Vec::new(),
            entries: Vec::new(),
            arrivals: Vec::new(),
            departures: Vec::new(),
            edge_callbacks: Vec::new(),
            movement: None,
            base_palette: Palette::default(),
            palette: Palette::default(),
            palette_mapping: std::array::from_fn(|index| index as u8),
            palette_adjustments: [0; 256],
            clear_color: 0,
            modal: None,
            action_selection: false,
            selected_record: None,
            study_expected: None,
            study_component: 0,
            study_navigation: None,
            study_success: None,
            menu_selection: 0,
            captain_presentation: [0; 3],
            character_presentation: [0; 3],
            mouse_x: 0,
            mouse_y: 0,
            confirm_latch: false,
            overlay_active: false,
            deferred_target: None,
            entry_dispatched: false,
        }
    }
}

pub struct Engine {
    archive: Archive,
    config: LaunchConfig,
    pub state: GameState,
    scene: Scene,
    framebuffer: Framebuffer,
    pending_scene: Option<(String, String)>,
    events: VecDeque<EngineEvent>,
    rng: u64,
    exited: bool,
}

impl Engine {
    pub fn open(mut config: LaunchConfig) -> Result<Self> {
        let policy_path = config.data_dir.join("SOUND.5");
        if policy_path.is_file() {
            config.apply_policy(InstallationPolicy::parse(&fs::read(policy_path)?)?);
        }
        let archive = Archive::open(config.data_dir.join("DD1.DAT"))?;
        let program = archive.read("LOGO.BIN")?;
        let mut state = GameState {
            translation: u16::from(config.translation),
            ..GameState::default()
        };
        state.scene_name = "LOGO".into();
        state.scene_entry = "seg".into();
        let mut engine = Self {
            archive,
            config,
            state,
            scene: Scene::new("LOGO".into(), program),
            framebuffer: Framebuffer::default(),
            pending_scene: None,
            events: VecDeque::new(),
            rng: 0x4342_4942_4c45,
            exited: false,
        };
        if let Ok(cursor) = engine.archive.read("RUN.ART") {
            engine.scene.art.push(Art::parse(&cursor)?);
        }
        engine.events.push_back(EngineEvent::SceneChanged {
            scene: "LOGO".into(),
            entry: "seg".into(),
        });
        Ok(engine)
    }

    pub fn archive(&self) -> &Archive {
        &self.archive
    }
    pub fn framebuffer(&self) -> &Framebuffer {
        &self.framebuffer
    }
    pub fn palette(&self) -> &Palette {
        &self.scene.palette
    }
    pub fn scene_name(&self) -> &str {
        &self.scene.name
    }
    pub fn actions(&self) -> impl Iterator<Item = (&str, i16, i16)> {
        let enabled = self.scene.action_selection;
        self.scene
            .actions
            .iter()
            .filter(move |item| enabled && item.active)
            .map(|item| (item.label.as_str(), item.x, item.y))
            .chain(
                self.scene
                    .actors
                    .iter()
                    .filter(move |actor| enabled && actor.action_enabled)
                    .map(|actor| (actor.selector.as_str(), actor.selector_x, actor.selector_y)),
            )
    }
    pub fn choice_count(&self) -> Option<usize> {
        matches!(self.scene.modal, Some(Modal::Choices { .. })).then_some(self.scene.choices.len())
    }
    pub fn study_active(&self) -> bool {
        matches!(self.scene.modal, Some(Modal::Study { .. }))
    }
    pub fn available_study_records(&self) -> Vec<StudyRecord> {
        self.state
            .text
            .as_ref()
            .map(|bank| {
                bank.descriptors
                    .iter()
                    .filter(|record| record.state != 0)
                    .map(|record| StudyRecord {
                        selector: record.selector,
                        citation: record.citation.clone(),
                        verse: record.verse.clone(),
                    })
                    .collect()
            })
            .unwrap_or_default()
    }
    pub fn take_events(&mut self) -> Vec<EngineEvent> {
        self.events.drain(..).collect()
    }

    pub fn status(&self) -> EngineStatus {
        if self.exited {
            EngineStatus::Exited
        } else if self.pending_scene.is_some() {
            EngineStatus::SceneTransition
        } else if self.scene.modal.is_some() {
            EngineStatus::AwaitingInput
        } else {
            EngineStatus::Running
        }
    }

    pub fn tick<I: IntoIterator<Item = InputEvent>>(&mut self, input: I) -> Result<EngineStatus> {
        self.tick_internal(input, true)
    }

    /// Advance multiple reference timer units while composing only the final
    /// framebuffer. Input is consumed on the first unit.
    pub fn tick_elapsed<I: IntoIterator<Item = InputEvent>>(
        &mut self,
        input: I,
        elapsed: usize,
    ) -> Result<EngineStatus> {
        if elapsed == 0 {
            return Ok(self.status());
        }
        self.tick_internal(input, elapsed == 1)?;
        for step in 1..elapsed {
            self.tick_internal([], step + 1 == elapsed)?;
        }
        Ok(self.status())
    }

    fn tick_internal<I: IntoIterator<Item = InputEvent>>(
        &mut self,
        input: I,
        render: bool,
    ) -> Result<EngineStatus> {
        for event in input {
            self.handle_input(event)?;
        }
        for animation in &mut self.scene.animations {
            animation.advance();
        }
        self.advance_movement()?;
        for thread in &mut self.scene.threads {
            if thread.delay < 0 {
                thread.delay = thread.delay.saturating_add(1);
            }
        }
        self.run_threads()?;
        if render {
            self.render()?;
        }
        if self.state.variables[21] < 0 {
            self.state.variables[21] = 0;
            self.pending_scene = Some(("OVER".into(), "seg".into()));
        }
        if let Some((name, entry)) = self.pending_scene.take() {
            self.enter_scene(name, entry)?;
        }
        Ok(self.status())
    }

    fn enter_scene(&mut self, name: String, entry: String) -> Result<()> {
        let resource = if name.to_ascii_uppercase().ends_with(".BIN") {
            name.clone()
        } else {
            format!("{name}.BIN")
        };
        let program = self.archive.read(&resource)?;
        self.state.scene_name = name.clone();
        self.state.scene_entry = entry.clone();
        self.scene = Scene::new(name.clone(), program);
        self.scene
            .art
            .push(Art::parse(&self.archive.read("RUN.ART")?)?);
        self.events
            .push_back(EngineEvent::SceneChanged { scene: name, entry });
        Ok(())
    }

    fn render(&mut self) -> Result<()> {
        self.framebuffer.fill(self.scene.clear_color);
        // Controller updates occur in separate routines in the DOS engine,
        // but each routine writes to the stable render slot allocated by the
        // mixed display list. The compositor paints those slots in display
        // order, allowing later scenery to occlude earlier moving actors.
        for object in &self.scene.display {
            if object.hidden {
                continue;
            }
            let fields = match object.source {
                DisplaySource::Direct {
                    frame,
                    art_slot,
                    x,
                    y,
                    scale,
                    flags,
                } => Some((frame, art_slot, x, y, scale, flags)),
                DisplaySource::Actor(index) => self.scene.actors.get(index).map(|actor| {
                    (
                        actor.frame,
                        actor.art_slot,
                        actor.x,
                        actor.y,
                        actor.scale,
                        actor.flags,
                    )
                }),
                DisplaySource::Animation(index) => {
                    self.scene
                        .animation_render_fields(index)
                        .map(|(step, x, y, scale)| {
                            (step.frame, step.art_slot, x, y, scale, step.flags)
                        })
                }
            };
            let Some((frame, art_slot, x, y, scale, flags)) = fields else {
                continue;
            };
            if frame == 0 || art_slot & 0x80 != 0 {
                continue;
            }
            let art = self
                .scene
                .art
                .get(usize::from(art_slot & 0x7f))
                .ok_or_else(|| {
                    EngineError::vm(
                        &self.scene.name,
                        0,
                        format!("ART slot {} is not loaded", art_slot & 0x7f),
                    )
                })?;
            let frame = art
                .frames
                .get(usize::from(frame - 1))
                .ok_or_else(|| EngineError::vm(&self.scene.name, 0, "ART frame is out of range"))?;
            self.framebuffer.draw(frame, x, y, scale, flags, true);
        }
        Ok(())
    }

    fn run_threads(&mut self) -> Result<()> {
        let mut budget = INSTRUCTION_BUDGET;
        for slot in 0..THREAD_COUNT {
            while self.scene.threads[slot].active
                && !self.scene.threads[slot].suspended
                && self.scene.threads[slot].delay >= 0
                && self.pending_scene.is_none()
            {
                if budget == 0 {
                    return Err(EngineError::vm(
                        &self.scene.name,
                        self.scene.threads[slot].ip,
                        "instruction budget exhausted",
                    ));
                }
                budget -= 1;
                let offset = self.scene.threads[slot].ip;
                let instruction = decode(&self.scene.program, offset).map_err(|error| {
                    EngineError::vm(&self.scene.name, offset, error.to_string())
                })?;
                self.scene.threads[slot].ip = instruction.end;
                if self.execute(slot, &instruction)? {
                    break;
                }
            }
        }
        Ok(())
    }

    fn handle_input(&mut self, event: InputEvent) -> Result<()> {
        match event {
            InputEvent::PointerMove { x, y } => {
                self.scene.mouse_x = x.clamp(0, 319);
                self.scene.mouse_y = y.clamp(0, 199);
            }
            InputEvent::PointerClick { x, y } => {
                self.scene.mouse_x = x.clamp(0, 319);
                self.scene.mouse_y = y.clamp(0, 199);
                if matches!(self.scene.modal, Some(Modal::Dialogue { .. })) {
                    self.resume_modal(None)?;
                } else if matches!(self.scene.modal, Some(Modal::Choices { .. })) {
                    self.resume_modal(self.default_choice())?;
                } else if !matches!(self.scene.modal, Some(Modal::Study { .. })) {
                    // A study result must identify a record; a bare click is
                    // not enough to manufacture a selector.
                    if let Some(selection) = self.nearest_action(x, y) {
                        self.start_selection(selection)?;
                    } else {
                        self.scene.confirm_latch = true;
                    }
                }
            }
            InputEvent::Confirm => {
                if matches!(self.scene.modal, Some(Modal::Dialogue { .. })) {
                    self.resume_modal(None)?;
                } else if matches!(self.scene.modal, Some(Modal::Choices { .. })) {
                    self.resume_modal(self.default_choice())?;
                } else if !matches!(self.scene.modal, Some(Modal::Study { .. })) {
                    self.scene.confirm_latch = true;
                }
            }
            InputEvent::Cancel => {
                if matches!(self.scene.modal, Some(Modal::Study { .. })) {
                    self.state.set_flag(0x14, false);
                    self.state.set_flag(0x15, true);
                    self.resume_modal(None)?;
                }
            }
            InputEvent::Choose(index) => self.resume_modal(Some(index))?,
            InputEvent::ApplyStudy(selector) => {
                if matches!(self.scene.modal, Some(Modal::Study { .. })) {
                    let success = self.scene.study_expected == Some(selector);
                    self.state.set_flag(0x14, success);
                    self.state.set_flag(0x15, !success);
                    self.resume_modal(None)?;
                    if success {
                        if let Some((expected, node)) = self.scene.study_navigation
                            && expected == selector
                        {
                            self.move_primary_actor(node, 0)?;
                        }
                        if let Some((expected, target, thread)) = self.scene.study_success
                            && expected == selector
                        {
                            let thread = self.thread_mut(thread, 0)?;
                            thread.ip = target;
                            thread.active = true;
                            thread.suspended = false;
                        }
                    }
                }
            }
            InputEvent::Action(label) => {
                if let Some(selection) = self.selection_by_label(&label) {
                    self.start_selection(selection)?;
                }
            }
            InputEvent::Key(key) => {
                let key = key.to_ascii_lowercase();
                if let Some(selection) = self.selection_by_key(key) {
                    self.start_selection(selection)?;
                }
            }
            InputEvent::QuickSave => self.quick_save()?,
            InputEvent::QuickLoad => self.quick_load()?,
        }
        Ok(())
    }

    fn nearest_action(&self, x: i16, y: i16) -> Option<Selection> {
        if !self.scene.action_selection {
            return None;
        }
        self.scene
            .actions
            .iter()
            .enumerate()
            .filter(|(_, action)| action.active)
            .map(|(index, action)| (Selection::Action(index), action.x, action.y))
            .chain(
                self.scene
                    .actors
                    .iter()
                    .enumerate()
                    .filter(|(_, actor)| actor.action_enabled)
                    .map(|(index, actor)| {
                        (Selection::Actor(index), actor.selector_x, actor.selector_y)
                    }),
            )
            .min_by_key(|(_, target_x, target_y)| {
                i32::from(*target_x - x).pow(2) + i32::from(*target_y - y).pow(2)
            })
            .map(|(selection, _, _)| selection)
    }

    fn default_choice(&self) -> Option<usize> {
        (!self.scene.choices.is_empty())
            .then(|| usize::from(self.scene.menu_selection).min(self.scene.choices.len() - 1))
    }

    fn selection_by_label(&self, label: &str) -> Option<Selection> {
        if !self.scene.action_selection {
            return None;
        }
        self.scene
            .actions
            .iter()
            .position(|action| action.active && action.label.eq_ignore_ascii_case(label))
            .map(Selection::Action)
            .or_else(|| {
                self.scene
                    .actors
                    .iter()
                    .position(|actor| {
                        actor.action_enabled && actor.selector.eq_ignore_ascii_case(label)
                    })
                    .map(Selection::Actor)
            })
    }

    fn selection_by_key(&self, key: char) -> Option<Selection> {
        self.actions()
            .enumerate()
            .find(|(_, (label, _, _))| {
                label
                    .chars()
                    .find(|value| value.is_ascii_alphabetic())
                    .is_some_and(|value| value.to_ascii_lowercase() == key)
            })
            .and_then(|(combined_index, _)| {
                let action_count = self
                    .scene
                    .actions
                    .iter()
                    .filter(|action| action.active)
                    .count();
                if combined_index < action_count {
                    self.scene
                        .actions
                        .iter()
                        .enumerate()
                        .filter(|(_, action)| action.active)
                        .nth(combined_index)
                        .map(|(index, _)| Selection::Action(index))
                } else {
                    self.scene
                        .actors
                        .iter()
                        .enumerate()
                        .filter(|(_, actor)| actor.action_enabled)
                        .nth(combined_index - action_count)
                        .map(|(index, _)| Selection::Actor(index))
                }
            })
    }

    fn start_selection(&mut self, selection: Selection) -> Result<()> {
        match selection {
            Selection::Action(index) => {
                if let Some(action) = self.scene.actions.get(index) {
                    self.scene.threads[0].ip = action.target;
                    self.scene.threads[0].active = true;
                    self.scene.threads[0].suspended = false;
                }
            }
            Selection::Actor(index) => {
                if self.scene.actors.get(index).is_some() {
                    self.move_primary_actor(index as u8, 0)?;
                }
            }
        }
        Ok(())
    }

    fn resume_modal(&mut self, selection: Option<usize>) -> Result<()> {
        let Some(modal) = self.scene.modal.take() else {
            return Ok(());
        };
        let owner = match modal {
            Modal::Dialogue { owner } | Modal::Choices { owner } | Modal::Study { owner } => owner,
        };
        if let Some(index) = selection {
            let target = self
                .scene
                .choices
                .get(index)
                .ok_or_else(|| EngineError::format("input", "choice is out of range"))?
                .target;
            self.scene.threads[owner].ip = target;
        }
        self.scene.threads[owner].active = true;
        self.scene.threads[owner].suspended = false;
        Ok(())
    }

    fn save_path(&self, suffix: &str) -> PathBuf {
        let mut path = self.config.player_prefix.clone();
        if path.is_relative() {
            path = self.config.data_dir.join(path);
        }
        PathBuf::from(format!("{}{suffix}", path.display()))
    }

    pub fn save_index(&self) -> Result<SaveIndex> {
        let path = self.save_path(".SV0");
        if path.is_file() {
            SaveIndex::parse(&fs::read(path)?)
        } else {
            Ok(SaveIndex::default())
        }
    }

    pub fn save_slot(&self, slot: u8, label: &str) -> Result<()> {
        if !(1..=9).contains(&slot) {
            return Err(EngineError::Usage("save slot must be 1 through 9".into()));
        }
        let mut index = self.save_index()?;
        index.labels[usize::from(slot - 1)] = if label.is_empty() {
            format!("Game {slot}")
        } else {
            label.to_owned()
        };
        let state = SaveImage::from_state(&self.state).encode()?;
        let labels = index.encode()?;
        atomic_write(&self.save_path(&format!(".SV{slot}")), &state)?;
        atomic_write(&self.save_path(".SV0"), &labels)
    }

    pub fn load_slot(&mut self, slot: u8) -> Result<()> {
        if !(1..=9).contains(&slot) {
            return Err(EngineError::Usage("save slot must be 1 through 9".into()));
        }
        self.load_image(&self.save_path(&format!(".SV{slot}")))
    }

    fn quick_save(&self) -> Result<()> {
        atomic_write(
            &self.save_path(".SVQ"),
            &SaveImage::from_state(&self.state).encode()?,
        )
    }

    fn quick_load(&mut self) -> Result<()> {
        self.load_image(&self.save_path(".SVQ"))
    }

    fn load_image(&mut self, path: &std::path::Path) -> Result<()> {
        let image = SaveImage::parse(&fs::read(path)?)?;
        let text = self.load_text_for(image.translation as u8, image.checkpoint.text_bank)?;
        self.state = image.into_state(text);
        self.state.restore_checkpoint();
        self.pending_scene = Some((
            self.state.scene_name.clone(),
            self.state.scene_entry.clone(),
        ));
        Ok(())
    }

    fn load_text_for(&self, translation: u8, bank: u8) -> Result<Option<TextBank>> {
        if bank == 0 {
            return Ok(None);
        }
        let name = format!("{}{}", translation_letter(translation)?, bank as char);
        let index = self.archive.read(&name)?;
        let companion = fs::read(self.config.data_dir.join(format!("DDL{}", bank as char)))?;
        Ok(Some(TextBank::parse(
            bank,
            &index,
            &companion,
            self.config.filter_mature,
        )?))
    }
}

impl Engine {
    /// Execute one decoded instruction. `true` yields the current scheduler
    /// invocation; `false` continues immediately.
    fn execute(&mut self, slot: usize, instruction: &Instruction) -> Result<bool> {
        let byte = |index: usize| -> u8 { instruction.operands[index].byte() };
        let word = |index: usize| -> u16 { instruction.operands[index].word() };
        let target = |index: usize| -> Result<usize> {
            let value = usize::from(word(index));
            if value >= self.scene.program.len() {
                Err(EngineError::vm(
                    &self.scene.name,
                    instruction.offset,
                    format!("target {value:#x} is out of range"),
                ))
            } else {
                Ok(value)
            }
        };
        let var = |engine: &Engine, encoded: u16| -> Result<i16> {
            engine
                .state
                .variable(encoded)
                .map_err(|message| EngineError::vm(&engine.scene.name, instruction.offset, message))
        };
        let set_var = |engine: &mut Engine, encoded: u16, value: i16| -> Result<()> {
            engine
                .state
                .set_variable(encoded, value)
                .map_err(|message| EngineError::vm(&engine.scene.name, instruction.offset, message))
        };
        let text = |engine: &Engine, index: usize| -> Result<String> {
            string_operand(&engine.scene.program, &instruction.operands[index]).map_err(|error| {
                EngineError::vm(&engine.scene.name, instruction.offset, error.to_string())
            })
        };

        match instruction.opcode {
            0x01 => {
                let name = resource_name(&text(self, 0)?, "ART");
                let art = Art::parse(&self.archive.read(&name)?)?;
                self.scene.art.push(art);
            }
            0x02 => {
                let actor_index = usize::from(byte(0));
                ensure_actor(&mut self.scene.actors, actor_index);
                let actor = &mut self.scene.actors[actor_index];
                actor.x = word(1) as i16;
                actor.y = word(2) as i16;
                actor.scale = word(3);
                ensure_navigation_node(
                    &mut self.scene.navigation_nodes,
                    actor_index,
                    NavigationNode {
                        x: actor.x,
                        y: actor.y,
                        scale: actor.scale,
                    },
                );
                self.scene.display.push(DisplayObject {
                    source: DisplaySource::Actor(actor_index),
                    hidden: false,
                });
            }
            0x03 | 0x04 | 0x43 => {
                let (scale, flags_index) = if instruction.opcode == 0x03 {
                    (0x100, 4)
                } else {
                    (word(4), 5)
                };
                self.scene.display.push(DisplayObject {
                    source: DisplaySource::Direct {
                        frame: byte(0),
                        art_slot: byte(1),
                        x: word(2) as i16,
                        y: word(3) as i16,
                        scale,
                        flags: byte(flags_index),
                    },
                    hidden: byte(1) & 0x80 != 0,
                });
            }
            0x05 => {
                if slot == 0 && !self.scene.entry_dispatched {
                    self.scene.entry_dispatched = true;
                    let requested = self.state.scene_entry.clone();
                    if let Some((from, to, _)) = self
                        .scene
                        .entries
                        .iter()
                        .find(|(_, _, name)| name.eq_ignore_ascii_case(&requested))
                        .cloned()
                    {
                        ensure_actor(&mut self.scene.actors, 0);
                        let (x, y, scale) = self
                            .scene
                            .navigation_nodes
                            .get(usize::from(from))
                            .and_then(Option::as_ref)
                            .map(|node| (node.x, node.y, node.scale))
                            .unwrap_or((
                                self.scene.actors[0].x,
                                self.scene.actors[0].y,
                                self.scene.actors[0].scale,
                            ));
                        let actor = &mut self.scene.actors[0];
                        actor.previous_node = from;
                        actor.node = from;
                        actor.x = x;
                        actor.y = y;
                        actor.scale = scale;
                        self.move_primary_actor(to, instruction.offset)?;
                        if self.scene.movement.is_some() {
                            return Ok(true);
                        }
                    }
                }
                self.scene.threads[slot].active = false;
                return Ok(true);
            }
            0x06 => {
                let index = self.scene.animations.len();
                self.scene.animations.push(Animation::new(word(0)));
                self.scene.display.push(DisplayObject {
                    source: DisplaySource::Animation(index),
                    hidden: false,
                });
            }
            0x07 => {
                let Operand::Record9(record) = instruction.operands[0] else {
                    unreachable!()
                };
                self.scene
                    .animations
                    .last_mut()
                    .ok_or_else(|| {
                        EngineError::vm(
                            &self.scene.name,
                            instruction.offset,
                            "animation step has no preceding sequence",
                        )
                    })?
                    .steps
                    .push(AnimationStep::parse(record));
            }
            0x08 => {
                self.start_animation(usize::from(byte(0)), byte(1), None, instruction.offset)?
            }
            0x09 => {
                let animation = self.animation_mut(usize::from(byte(0)), instruction.offset)?;
                animation.state = 0;
            }
            0x0a => {
                let state = self.scene.threads[0].motion_state;
                if !matches!(state, 0 | 2) {
                    self.scene.threads[slot].ip = instruction.offset;
                    return Ok(true);
                }
            }
            0x0b => self.scene.navigation_edges.push((byte(0), byte(1))),
            0x0c => self.scene.entries.push((byte(0), byte(1), text(self, 2)?)),
            0x0d => {
                let name = text(self, 0)?;
                let entry = text(self, 1)?;
                self.pending_scene = Some((name, entry));
                return Ok(true);
            }
            0x0e | 0x4a | 0x4b | 0x56 | 0x60 => {}
            0x0f => {
                self.scene.threads[slot].delay =
                    self.scene.threads[slot].delay.wrapping_sub(word(0) as i16)
            }
            0x10 => {
                let actor_index = usize::from(byte(0));
                let selector = text(self, 3)?;
                ensure_actor(&mut self.scene.actors, actor_index);
                let actor = &mut self.scene.actors[actor_index];
                actor.selector_x = word(1) as i16;
                actor.selector_y = word(2) as i16;
                actor.selector = selector;
            }
            0x11 | 0x12 | 0x17 | 0x18 | 0x19 | 0x1a => {
                let raw = word(1) as i16;
                let (thread, callback_target) = if raw < 0 {
                    (Some((-raw) as usize), usize::from(word(2)))
                } else {
                    (None, raw as usize)
                };
                if callback_target >= self.scene.program.len() {
                    return Err(EngineError::vm(
                        &self.scene.name,
                        instruction.offset,
                        "callback target is out of range",
                    ));
                }
                if instruction.opcode == 0x11 || instruction.opcode == 0x12 {
                    let callback = Callback {
                        selector: byte(0),
                        target: callback_target,
                        thread,
                    };
                    if instruction.opcode == 0x11 {
                        self.scene.arrivals.push(callback);
                    } else {
                        self.scene.departures.push(callback);
                    }
                } else {
                    let phase = match instruction.opcode {
                        0x17 => EdgeCallbackPhase::ReverseDeparture,
                        0x18 => EdgeCallbackPhase::ForwardDeparture,
                        0x19 => EdgeCallbackPhase::ForwardArrival,
                        0x1a => EdgeCallbackPhase::ReverseArrival,
                        _ => unreachable!(),
                    };
                    self.scene.edge_callbacks.push(EdgeCallback {
                        edge: byte(0),
                        phase,
                        target: callback_target,
                        thread,
                    });
                }
            }
            0x13 => {
                let wanted = usize::from(word(0));
                if let Some(index) = self
                    .scene
                    .choices
                    .iter()
                    .position(|choice| choice.target == wanted)
                {
                    self.scene.choices.remove(index);
                }
            }
            0x14 | 0x48 | 0x4e => {
                if self.scene.modal.is_some() {
                    self.scene.threads[slot].ip = instruction.offset;
                    return Ok(true);
                }
                let channel = match instruction.opcode {
                    0x14 => DialogueChannel::Adversary,
                    0x48 => DialogueChannel::Character,
                    _ => DialogueChannel::CaptainBible,
                };
                let value = self.expand_dialogue(&text(self, 0)?);
                self.scene.modal = Some(Modal::Dialogue { owner: slot });
                self.scene.threads[slot].suspended = true;
                self.events.push_back(EngineEvent::Dialogue {
                    channel,
                    text: value,
                });
                return Ok(true);
            }
            0x15 => {
                self.scene.selected_record = Some(byte(0));
                self.scene.study_expected = Some(byte(0));
                self.scene.study_navigation = None;
                self.scene.study_success = None;
            }
            0x16 => {
                let first = usize::from(word(0));
                let last = usize::from(word(1));
                let value = var(self, word(2))?;
                if first > last || last >= 256 {
                    return Err(EngineError::vm(
                        &self.scene.name,
                        instruction.offset,
                        "palette range is invalid",
                    ));
                }
                self.scene.palette_adjustments[first..=last].fill(value);
                self.refresh_palette();
            }
            0x1b => self.scene.threads[0].delay = (word(0) as i16).wrapping_neg(),
            0x1c | 0x1d => {
                let index = usize::from(byte(0));
                ensure_actor(&mut self.scene.actors, index);
                self.scene.actors[index].action_enabled = instruction.opcode == 0x1c;
            }
            0x1e => {
                let value = var(self, word(0))?;
                set_var(self, word(1), value)?;
            }
            0x1f => set_var(self, word(1), word(0) as i16)?,
            0x20 | 0x21 => {
                let zero = var(self, word(0))? == 0;
                if zero == (instruction.opcode == 0x20) {
                    self.scene.threads[slot].ip = target(1)?;
                }
            }
            0x22..=0x29 => {
                let left = var(self, word(0))?;
                let right = if matches!(instruction.opcode, 0x22 | 0x24 | 0x26 | 0x28) {
                    var(self, word(1))?
                } else {
                    word(1) as i16
                };
                let branch = match instruction.opcode {
                    0x22 | 0x23 => left == right,
                    0x24 | 0x25 => left != right,
                    0x26 | 0x27 => left > right,
                    0x28 | 0x29 => left < right,
                    _ => unreachable!(),
                };
                if branch {
                    self.scene.threads[slot].ip = target(2)?;
                }
            }
            0x2a..=0x31 => {
                let destination = word(1);
                let left = var(self, destination)?;
                let right = if matches!(instruction.opcode, 0x2a | 0x2c | 0x2e | 0x30) {
                    var(self, word(0))?
                } else {
                    word(0) as i16
                };
                let value = match instruction.opcode {
                    0x2a | 0x2b => left.wrapping_add(right),
                    0x2c | 0x2d => left.wrapping_sub(right),
                    0x2e | 0x2f => ((i32::from(left) * i32::from(right)) as u16) as i16,
                    0x30 | 0x31 => {
                        if right == 0 {
                            return Err(EngineError::vm(
                                &self.scene.name,
                                instruction.offset,
                                "division by zero",
                            ));
                        }
                        ((i32::from(left) / i32::from(right)) as u16) as i16
                    }
                    _ => unreachable!(),
                };
                set_var(self, destination, value)?;
            }
            0x32 | 0x33 => {
                let old = var(self, word(0))?;
                set_var(
                    self,
                    word(0),
                    if instruction.opcode == 0x32 {
                        old.wrapping_add(1)
                    } else {
                        old.wrapping_sub(1)
                    },
                )?;
            }
            0x34 => {
                self.scene.threads[slot].calls.push(instruction.end);
                self.scene.threads[slot].ip = target(0)?;
            }
            0x35 => {
                if let Some(return_to) = self.scene.threads[slot].calls.pop() {
                    self.scene.threads[slot].ip = return_to;
                } else {
                    self.scene.threads[slot].active = false;
                    return Ok(true);
                }
            }
            0x36 | 0x37 => {
                let selector = byte(0);
                self.scene.selected_record = Some(selector);
                if let Some(record) = self
                    .state
                    .text
                    .as_mut()
                    .and_then(|text| text.by_selector_mut(selector))
                {
                    record.state = u8::from(instruction.opcode == 0x36);
                }
            }
            0x38 | 0x39 => {
                let set = self
                    .state
                    .text
                    .as_ref()
                    .and_then(|text| text.by_selector(byte(0)))
                    .is_some_and(|record| record.state != 0);
                if set == (instruction.opcode == 0x38) {
                    self.scene.threads[slot].ip = target(1)?;
                }
            }
            0x3a => self.scene.actions.push(ActionTarget {
                target: target(0)?,
                x: word(1) as i16,
                y: word(2) as i16,
                label: text(self, 3)?,
                active: false,
            }),
            0x3b | 0x3c => {
                let index = usize::from(byte(0));
                let action = self.scene.actions.get_mut(index).ok_or_else(|| {
                    EngineError::vm(
                        &self.scene.name,
                        instruction.offset,
                        "action index is out of range",
                    )
                })?;
                action.active = instruction.opcode == 0x3b;
            }
            0x3d => self.scene.threads[slot].ip = target(0)?,
            0x3e => {
                let target = target(1)?;
                let thread = self.thread_mut(usize::from(byte(0)), instruction.offset)?;
                thread.ip = target;
                thread.active = true;
                thread.suspended = false;
            }
            0x3f => {
                if !self
                    .animation(usize::from(byte(0)), instruction.offset)?
                    .finished()
                {
                    self.scene.threads[slot].ip = instruction.offset;
                    return Ok(true);
                }
            }
            0x40 => {
                self.scene.threads[slot].motion_state = byte(0);
            }
            0x41 => self.scene.action_selection = true,
            0x42 => self.scene.action_selection = false,
            0x44 => self.scene.choices.push(Choice {
                target: target(0)?,
                text: text(self, 1)?,
            }),
            0x45 => {
                self.scene.choices.clear();
                self.scene.modal = None;
            }
            0x46 => {
                self.scene.modal = Some(Modal::Choices { owner: slot });
                self.scene.threads[slot].suspended = true;
                self.events.push_back(EngineEvent::Choices(
                    self.scene
                        .choices
                        .iter()
                        .map(|choice| choice.text.clone())
                        .collect(),
                ));
                return Ok(true);
            }
            0x47 => self.scene.menu_selection = byte(0),
            0x49 => {
                self.state.set_flag(0x14, false);
                self.state.set_flag(0x15, false);
                self.scene.modal = Some(Modal::Study { owner: slot });
                self.scene.threads[slot].suspended = true;
                self.events.push_back(EngineEvent::StudyRequested {
                    expected_selector: self.scene.study_expected,
                    prompt_component: self.scene.study_component,
                });
                return Ok(true);
            }
            0x4c => self.scene.clear_color = byte(0),
            0x4d | 0x6d => {
                let name = resource_name(&text(self, 0)?, "PAL");
                self.scene.base_palette = Palette::parse(&self.archive.read(&name)?)?;
                self.scene.palette_mapping = std::array::from_fn(|index| index as u8);
                self.scene.palette_adjustments.fill(0);
                self.refresh_palette();
            }
            0x4f => {
                self.scene.study_expected = Some(byte(0));
                self.scene.study_navigation = Some((byte(0), byte(1)));
                self.scene.study_success = None;
            }
            0x50 => {
                self.scene.study_expected = None;
                self.scene.selected_record = None;
                self.scene.study_navigation = None;
                self.scene.study_success = None;
            }
            0x51 => {
                self.scene.study_expected = Some(byte(0));
                self.scene.study_navigation = None;
                self.scene.study_success = Some((byte(0), target(1)?, usize::from(byte(2))));
            }
            0x52 => {
                if self.state.music_enabled != 0 {
                    self.events.push_back(EngineEvent::Music(byte(0)));
                }
            }
            0x53 => {
                let node = byte(0);
                let (x, y, scale) = self.navigation_node(node, instruction.offset)?;
                ensure_actor(&mut self.scene.actors, 0);
                let actor = &mut self.scene.actors[0];
                actor.node = node;
                actor.previous_node = node;
                actor.x = x;
                actor.y = y;
                actor.scale = scale;
                actor.animation_phase = 0x200;
                set_actor_render_state(actor, false);
            }
            0x54 => self.move_primary_actor(byte(0), instruction.offset)?,
            0x55 => self.state.snapshot(),
            0x57 => {
                let number = byte(0);
                let rate = word(1);
                if number != 0 || rate != 0 {
                    Effect::decode(&self.archive.read(&format!("D{number:03}.ABT"))?)?;
                    if self.state.effects_enabled != 0 {
                        self.events.push_back(EngineEvent::Sound(number));
                    }
                }
            }
            // There is no PCM output backend yet, so stopping playback is a
            // no-op just as it is on the reference engine's no-driver path.
            0x58 => {}
            0x59 => {
                // Without a usable digital backend, the reference subtracts
                // 100 from this thread's delay and resumes after the wait.
                self.scene.threads[slot].delay = self.scene.threads[slot].delay.wrapping_sub(100);
                return Ok(true);
            }
            0x5a => {
                // The current host has no PCM playback backend. The reference
                // jumps when the driver is absent, effects are disabled, its
                // ready bit is clear, or its explicit fallback word is set.
                self.scene.threads[slot].ip = target(0)?;
            }
            0x5b => {
                ensure_actor(&mut self.scene.actors, 0);
                let actor = &mut self.scene.actors[0];
                actor.direction = byte(0) & 3;
                set_actor_render_state(actor, self.scene.movement.is_some());
            }
            0x5c | 0x5d => {
                let presentation = [byte(0), byte(1), byte(2)];
                if instruction.opcode == 0x5c {
                    self.scene.captain_presentation = presentation;
                } else {
                    self.scene.character_presentation = presentation;
                }
            }
            0x5e => self.scene.deferred_target = Some(target(0)?),
            0x5f => self.start_animation(
                usize::from(byte(0)),
                byte(2),
                Some(usize::from(byte(1))),
                instruction.offset,
            )?,
            0x61 => {
                self.thread_mut(usize::from(byte(0)), instruction.offset)?
                    .active = false
            }
            0x62 => set_var(self, word(0), self.scene.mouse_x)?,
            0x63 => set_var(self, word(0), self.scene.mouse_y)?,
            0x64 => {
                if std::mem::take(&mut self.scene.confirm_latch) {
                    self.scene.threads[slot].ip = target(0)?;
                }
            }
            0x65 => {
                let first = usize::from(byte(0));
                let count = usize::from(byte(1));
                for object in self
                    .scene
                    .display
                    .get_mut(first..first.saturating_add(count))
                    .ok_or_else(|| {
                        EngineError::vm(
                            &self.scene.name,
                            instruction.offset,
                            "display range is out of bounds",
                        )
                    })?
                {
                    set_display_frame(object, 0);
                }
            }
            0x66 => {
                let first = usize::from(byte(0));
                let count = usize::from(byte(1));
                let minimum = byte(2);
                let maximum = byte(3);
                for object in self
                    .scene
                    .display
                    .get_mut(first..first.saturating_add(count))
                    .ok_or_else(|| {
                        EngineError::vm(
                            &self.scene.name,
                            instruction.offset,
                            "display range is out of bounds",
                        )
                    })?
                {
                    let next = display_frame(object).wrapping_add(1);
                    set_display_frame(
                        object,
                        if (minimum..=maximum).contains(&next) {
                            next
                        } else {
                            minimum
                        },
                    );
                }
            }
            0x67 => {
                self.events.push_back(EngineEvent::RestoreRequested);
                self.scene.threads[slot].suspended = true;
                return Ok(true);
            }
            0x68 => {
                let mut value = var(self, word(0))?;
                if value > 640 {
                    value = value.wrapping_sub(1280);
                }
                if value < -639 {
                    value = value.wrapping_add(1280);
                }
                set_var(self, word(0), value)?;
            }
            0x69 => {
                let value = self.program_word(usize::from(word(0)), instruction.offset)? as i16;
                set_var(self, word(1), value)?;
            }
            0x6a => {
                let value = var(self, word(1))? as u16;
                self.patch_program_word(usize::from(word(0)), value, instruction.offset)?;
            }
            0x6b => {
                let bank = byte(0);
                if self.state.text_bank != bank {
                    self.state.text = self.load_text_for(self.state.translation as u8, bank)?;
                    self.state.text_bank = bank;
                }
            }
            0x6c => {
                let minimum = word(0) as i16;
                let maximum = word(1) as i16;
                let step = word(2) as i16;
                let encoded = word(3);
                if minimum > maximum || minimum < 0 || maximum > 255 {
                    return Err(EngineError::vm(
                        &self.scene.name,
                        instruction.offset,
                        "palette rotation range is invalid",
                    ));
                }
                let mut phase = var(self, encoded)?.wrapping_add(step);
                while phase > maximum {
                    phase = minimum;
                }
                while phase < minimum {
                    phase = maximum;
                }
                set_var(self, encoded, phase)?;
                let mut source = phase;
                for destination in minimum..=maximum {
                    self.scene.palette_mapping[destination as usize] = source as u8;
                    source = source.wrapping_add(1);
                    if source > maximum {
                        source = minimum;
                    }
                }
                self.refresh_palette();
            }
            0x6e => self.scene.overlay_active = true,
            0x6f => {
                if self.scene.overlay_active {
                    self.scene.threads[slot].ip = instruction.offset;
                    return Ok(true);
                }
            }
            0x70 => {
                self.scene.art.pop();
            }
            0x71 => {
                let offset = var(self, word(0))? as u16 as usize;
                let value = self.program_word(offset, instruction.offset)?;
                set_var(self, word(1), value as i16)?;
            }
            0x72 => return Ok(true),
            0x73 | 0x74 => {
                let set = self.state.flag(byte(0));
                if set == (instruction.opcode == 0x74) {
                    self.scene.threads[slot].ip = target(1)?;
                }
            }
            0x75 | 0x76 => self.state.set_flag(byte(0), instruction.opcode == 0x76),
            0x77 => self.process_current_cell(instruction.offset)?,
            0x78 => {
                let level = byte(0) as char;
                let difficulty = *b"END"
                    .get(self.state.variables[0] as usize)
                    .ok_or_else(|| {
                        EngineError::vm(
                            &self.scene.name,
                            instruction.offset,
                            "difficulty is out of range",
                        )
                    })? as char;
                self.state.world =
                    WorldMap::parse(&self.archive.read(&format!("{level}{difficulty}.MAP"))?)?;
                self.state.variables[16] = level as i16;
            }
            0x79 => {
                self.scene.navigation_edges.clear();
                self.scene.entries.clear();
                self.scene.arrivals.clear();
                self.scene.departures.clear();
                self.scene.edge_callbacks.clear();
                self.scene.movement = None;
            }
            0x7a => {
                let value = var(self, word(1))? as u8;
                let offset = usize::from(word(0));
                *self.scene.program.get_mut(offset).ok_or_else(|| {
                    EngineError::vm(
                        &self.scene.name,
                        instruction.offset,
                        "BIN byte patch is out of range",
                    )
                })? = value;
            }
            0x7b => {
                let (x, y) = self.map_coordinates(instruction.offset)?;
                self.state
                    .world
                    .set_kind_unmasked(x, y, var(self, word(0))? as u8)?;
            }
            0x7c => {
                let (x, y) = self.map_coordinates(instruction.offset)?;
                self.state
                    .world
                    .set_parameter_a(x, y, var(self, word(0))? as u8)?;
            }
            0x7d => {
                self.scene.study_component = byte(0);
                self.scene.study_expected = Some(var(self, word(1))? as u8);
            }
            0x7e => self.scene.palette.black(),
            0x7f => {
                let (x, y) = self.map_coordinates(instruction.offset)?;
                self.state
                    .world
                    .set_parameter_b(x, y, var(self, word(0))? as u8)?;
            }
            0x80 => {
                if self
                    .animation(usize::from(byte(0)), instruction.offset)?
                    .state
                    != 0
                {
                    self.scene.threads[slot].ip = target(1)?;
                }
            }
            0x81 => {
                if !self.config.no_combat {
                    let base = word(0) as i16;
                    let loss = match self.state.variables[0] {
                        0 => base / 2,
                        1 => base,
                        2 => base.wrapping_mul(4),
                        _ => {
                            return Err(EngineError::vm(
                                &self.scene.name,
                                instruction.offset,
                                "difficulty is out of range",
                            ));
                        }
                    };
                    self.state.variables[21] = self.state.variables[21].wrapping_sub(loss);
                }
            }
            0x82 => {
                let modulus = word(0);
                if modulus == 0 {
                    return Err(EngineError::vm(
                        &self.scene.name,
                        instruction.offset,
                        "random modulus is zero",
                    ));
                }
                self.next_random();
                set_var(self, word(1), (self.rng % u64::from(modulus)) as i16)?;
            }
            0x83 => {
                let selector = var(self, word(0))? as u8;
                let component = byte(1);
                let destination = usize::from(word(2));
                let record = self
                    .state
                    .text
                    .as_ref()
                    .and_then(|bank| bank.by_selector(selector))
                    .cloned();
                let bytes = match (component, record) {
                    (b'X', Some(record)) => {
                        let wrong = record
                            .components
                            .iter()
                            .filter(|value| value.tag == b'W')
                            .count();
                        let mut order: Vec<u8> = (0..wrong as u8).collect();
                        order.push(b'C');
                        for _ in 0..20 {
                            self.next_random();
                            let left = self.rng as usize % order.len();
                            self.next_random();
                            let right = self.rng as usize % order.len();
                            order.swap(left, right);
                        }
                        self.state.variables[27] = order.len() as i16;
                        Some(order)
                    }
                    (b'V', Some(record)) => {
                        let value = format!("{} - {}", record.citation, record.verse);
                        let mut bytes = crate::text::encode_cp437(&value)?;
                        bytes.push(0);
                        Some(bytes)
                    }
                    (index @ 0..=9, Some(record)) => record
                        .components
                        .iter()
                        .filter(|value| value.tag == b'W')
                        .nth(usize::from(index))
                        .map(|value| value.text.as_str())
                        .map(crate::text::encode_cp437)
                        .transpose()?
                        .map(|mut bytes| {
                            bytes.push(0);
                            bytes
                        }),
                    (tag, Some(record)) => record
                        .components
                        .iter()
                        .find(|value| value.tag == tag)
                        .map(|value| value.text.as_str())
                        .map(crate::text::encode_cp437)
                        .transpose()?
                        .map(|mut bytes| {
                            bytes.push(0);
                            bytes
                        }),
                    (_, None) => None,
                };
                self.state.set_flag(0x22, bytes.is_some());
                if let Some(bytes) = bytes {
                    let target = self
                        .scene
                        .program
                        .get_mut(destination..destination + bytes.len())
                        .ok_or_else(|| {
                            EngineError::vm(
                                &self.scene.name,
                                instruction.offset,
                                "text copy exceeds BIN",
                            )
                        })?;
                    target.copy_from_slice(&bytes);
                }
            }
            0x84 => {
                let offset = usize::from(word(0));
                let value = *self.scene.program.get(offset).ok_or_else(|| {
                    EngineError::vm(
                        &self.scene.name,
                        instruction.offset,
                        "BIN byte read is out of range",
                    )
                })? as i8 as i16;
                set_var(self, word(1), value)?;
            }
            0x85 | 0x86 => {
                let object = self
                    .scene
                    .display
                    .get_mut(usize::from(byte(0)))
                    .ok_or_else(|| {
                        EngineError::vm(
                            &self.scene.name,
                            instruction.offset,
                            "display index is out of range",
                        )
                    })?;
                object.hidden = instruction.opcode == 0x85;
            }
            0x87 => self.state.world.normalize(),
            0x88 => {
                if let Some(text) = &mut self.state.text {
                    for descriptor in &mut text.descriptors {
                        descriptor.state = 0;
                    }
                }
            }
            0x89 => {
                let (x, y) = self.map_coordinates(instruction.offset)?;
                self.state.variables[37 + y] =
                    (self.state.variables[37 + y] as u16 | (1 << x)) as i16;
            }
            0x8a => {
                if self
                    .animation(usize::from(byte(0)), instruction.offset)?
                    .finished()
                {
                    self.scene.threads[slot].ip = target(1)?;
                }
            }
            0x8b => {
                if self.state.variables[0] == 2 {
                    let candidates: Vec<usize> = self
                        .state
                        .text
                        .as_ref()
                        .map(|bank| {
                            bank.descriptors
                                .iter()
                                .enumerate()
                                .filter(|(_, record)| record.state != 0)
                                .map(|(index, _)| index)
                                .collect()
                        })
                        .unwrap_or_default();
                    if !candidates.is_empty() {
                        self.rng = self.rng.wrapping_mul(6364136223846793005).wrapping_add(1);
                        if let Some(text) = &mut self.state.text {
                            text.descriptors[candidates[self.rng as usize % candidates.len()]]
                                .state = 0;
                        }
                    }
                }
            }
            0x8c => {
                if self.config.no_combat {
                    self.scene.threads[slot].ip = target(0)?;
                }
            }
            0x8d => {
                if !self.save_path(".SV0").is_file() {
                    self.scene.threads[slot].ip = target(0)?;
                }
            }
            0x8e => {
                let (x, y) = self.map_coordinates(instruction.offset)?;
                let value = self.state.auxiliary_cells[y * 16 + x];
                for bit in 0..5 {
                    self.state.set_flag(0x23 + bit, value & (1 << bit) != 0);
                }
            }
            0x8f => {
                let value = var(self, word(1))?;
                let destination = word(0);
                set_var(self, destination, var(self, destination)? & value)?;
            }
            0x90 => {
                let destination = word(1);
                set_var(self, destination, var(self, destination)? & word(0) as i16)?;
            }
            0x91 => {
                let divisor = word(0) as i16;
                if divisor == 0 {
                    return Err(EngineError::vm(
                        &self.scene.name,
                        instruction.offset,
                        "cell-byte divisor is zero",
                    ));
                }
                let (x, y) = self.map_coordinates(instruction.offset)?;
                set_var(
                    self,
                    word(1),
                    i16::from(self.state.auxiliary_cells[y * 16 + x]) % divisor,
                )?;
            }
            _ => {
                return Err(EngineError::vm(
                    &self.scene.name,
                    instruction.offset,
                    format!("unimplemented opcode {:#x}", instruction.opcode),
                ));
            }
        }
        Ok(false)
    }

    fn animation(&self, index: usize, offset: usize) -> Result<&Animation> {
        self.scene.animations.get(index).ok_or_else(|| {
            EngineError::vm(&self.scene.name, offset, "animation index is out of range")
        })
    }
    fn animation_mut(&mut self, index: usize, offset: usize) -> Result<&mut Animation> {
        self.scene.animations.get_mut(index).ok_or_else(|| {
            EngineError::vm(&self.scene.name, offset, "animation index is out of range")
        })
    }
    fn start_animation(
        &mut self,
        index: usize,
        state: u8,
        linked: Option<usize>,
        offset: usize,
    ) -> Result<()> {
        if let Some(linked) = linked
            && linked >= self.scene.animations.len()
        {
            return Err(EngineError::vm(
                &self.scene.name,
                offset,
                "linked animation index is out of range",
            ));
        }
        self.animation_mut(index, offset)?
            .start(state, linked)
            .map_err(|error| EngineError::vm(&self.scene.name, offset, error.to_string()))
    }
    fn thread_mut(&mut self, index: usize, offset: usize) -> Result<&mut Thread> {
        self.scene.threads.get_mut(index).ok_or_else(|| {
            EngineError::vm(&self.scene.name, offset, "thread index is out of range")
        })
    }

    fn program_word(&self, offset: usize, command: usize) -> Result<u16> {
        let bytes = self.scene.program.get(offset..offset + 2).ok_or_else(|| {
            EngineError::vm(&self.scene.name, command, "BIN word read is out of range")
        })?;
        Ok(u16::from_le_bytes([bytes[0], bytes[1]]))
    }
    fn patch_program_word(&mut self, offset: usize, value: u16, command: usize) -> Result<()> {
        let bytes = self
            .scene
            .program
            .get_mut(offset..offset + 2)
            .ok_or_else(|| {
                EngineError::vm(&self.scene.name, command, "BIN word patch is out of range")
            })?;
        bytes.copy_from_slice(&value.to_le_bytes());
        Ok(())
    }

    fn map_coordinates(&self, offset: usize) -> Result<(usize, usize)> {
        let x = self.state.variables[11];
        let y = self.state.variables[12];
        if x < 0 || x >= MAP_WIDTH as i16 || y < 0 || y >= MAP_HEIGHT as i16 {
            Err(EngineError::vm(
                &self.scene.name,
                offset,
                format!("map coordinate ({x},{y}) is out of range"),
            ))
        } else {
            Ok((x as usize, y as usize))
        }
    }

    fn process_current_cell(&mut self, offset: usize) -> Result<()> {
        let (x, y) = self.map_coordinates(offset)?;
        let context = self.state.world.context(x, y)?;
        self.state.variables[13] = context.kind_or_room_class;
        if let Some(value) = context.entrance_or_neighbor {
            self.state.variables[14] = value;
        }
        if let Some(value) = context.second_forward_kind {
            self.state.variables[15] = value;
        }
        self.state.variables[17] = context.parameter_a;
        self.state.variables[18] = context.parameter_b;
        self.state.variables[23..26].copy_from_slice(&context.adjacent_room_b);
        for flag in 0..0x30 {
            self.state.set_flag(flag, context.flags[usize::from(flag)]);
        }
        Ok(())
    }

    fn move_primary_actor(&mut self, destination: u8, offset: usize) -> Result<()> {
        ensure_actor(&mut self.scene.actors, 0);
        let start = self.scene.actors[0].node;
        let Some(route) = find_route(&self.scene.navigation_edges, start, destination) else {
            return Ok(());
        };
        if route.is_empty() {
            self.scene.threads[0].motion_state = 2;
            return Ok(());
        }
        let first = route[0];
        let (end_x, end_y, end_scale) = self.navigation_node(first.to, offset)?;
        let actor = &self.scene.actors[0];
        let duration_steps =
            movement_duration(actor.x, actor.y, actor.scale, end_x, end_y, end_scale);
        self.scene.movement = Some(Movement {
            route,
            current: 0,
            elapsed_units: 0,
            completed_steps: 0,
            duration_steps,
            start_x: actor.x,
            start_y: actor.y,
            start_scale: actor.scale,
            end_x,
            end_y,
            end_scale,
        });
        prepare_actor_for_edge(&mut self.scene.actors[0], end_x, end_scale);
        self.scene.threads[0].motion_state = 1;
        self.dispatch_navigation_callbacks(first, false, offset)?;
        Ok(())
    }

    fn advance_movement(&mut self) -> Result<()> {
        let Some(mut movement) = self.scene.movement.take() else {
            return Ok(());
        };
        movement.elapsed_units = movement.elapsed_units.saturating_add(1);
        let completed_steps =
            (movement.elapsed_units / MOVEMENT_STEP_UNITS).min(movement.duration_steps);
        let actor = &mut self.scene.actors[0];
        while movement.completed_steps < completed_steps {
            actor.animation_phase =
                (actor.animation_phase + RUN_PHASE_INCREMENT) % RUN_PHASE_PERIOD;
            movement.completed_steps += 1;
        }
        set_actor_render_state(actor, true);
        actor.x = lerp_i16(
            movement.start_x,
            movement.end_x,
            completed_steps,
            movement.duration_steps,
        );
        actor.y = lerp_i16(
            movement.start_y,
            movement.end_y,
            completed_steps,
            movement.duration_steps,
        );
        actor.scale = lerp_u16(
            movement.start_scale,
            movement.end_scale,
            completed_steps,
            movement.duration_steps,
        );
        if completed_steps < movement.duration_steps {
            self.scene.movement = Some(movement);
            return Ok(());
        }

        let completed = movement.route[movement.current];
        actor.previous_node = completed.from;
        actor.node = completed.to;
        actor.animation_phase = 0x200;
        set_actor_render_state(actor, false);
        self.dispatch_navigation_callbacks(completed, true, 0)?;
        movement.current += 1;
        if movement.current >= movement.route.len() {
            self.scene.threads[0].motion_state = 2;
            return Ok(());
        }

        let next = movement.route[movement.current];
        let (end_x, end_y, end_scale) = self.navigation_node(next.to, 0)?;
        let actor = &self.scene.actors[0];
        movement.start_x = actor.x;
        movement.start_y = actor.y;
        movement.start_scale = actor.scale;
        movement.end_x = end_x;
        movement.end_y = end_y;
        movement.end_scale = end_scale;
        movement.elapsed_units = 0;
        movement.completed_steps = 0;
        movement.duration_steps =
            movement_duration(actor.x, actor.y, actor.scale, end_x, end_y, end_scale);
        prepare_actor_for_edge(&mut self.scene.actors[0], end_x, end_scale);
        self.dispatch_navigation_callbacks(next, false, 0)?;
        self.scene.movement = Some(movement);
        Ok(())
    }

    fn navigation_node(&self, node: u8, offset: usize) -> Result<(i16, i16, u16)> {
        self.scene
            .navigation_nodes
            .get(usize::from(node))
            .and_then(Option::as_ref)
            .map(|node| (node.x, node.y, node.scale))
            .ok_or_else(|| {
                EngineError::vm(
                    &self.scene.name,
                    offset,
                    format!("navigation node {node} has no scene-thread geometry"),
                )
            })
    }

    fn dispatch_navigation_callbacks(
        &mut self,
        edge: RouteEdge,
        arrival: bool,
        offset: usize,
    ) -> Result<()> {
        let stored = self.scene.navigation_edges[edge.index];
        let forward = stored == (edge.from, edge.to);
        let phase = match (forward, arrival) {
            (true, false) => EdgeCallbackPhase::ForwardDeparture,
            (false, false) => EdgeCallbackPhase::ReverseDeparture,
            (true, true) => EdgeCallbackPhase::ForwardArrival,
            (false, true) => EdgeCallbackPhase::ReverseArrival,
        };
        let mut callbacks: Vec<(usize, Option<usize>)> = self
            .scene
            .edge_callbacks
            .iter()
            .filter(|callback| usize::from(callback.edge) == edge.index && callback.phase == phase)
            .map(|callback| (callback.target, callback.thread))
            .collect();
        let node = if arrival { edge.to } else { edge.from };
        let node_callbacks = if arrival {
            &self.scene.arrivals
        } else {
            &self.scene.departures
        };
        callbacks.extend(
            node_callbacks
                .iter()
                .filter(|callback| callback.selector == node)
                .map(|callback| (callback.target, callback.thread)),
        );
        for (target, thread) in callbacks {
            let thread = thread.unwrap_or(0);
            if thread >= THREAD_COUNT {
                return Err(EngineError::vm(
                    &self.scene.name,
                    offset,
                    "navigation callback thread is out of range",
                ));
            }
            let scheduler = &mut self.scene.threads[thread];
            scheduler.ip = target;
            scheduler.active = true;
            scheduler.suspended = false;
            scheduler.delay = 0;
        }
        Ok(())
    }

    fn expand_dialogue(&self, value: &str) -> String {
        let Some(selector) = self.scene.selected_record else {
            return value.to_owned();
        };
        let Some(record) = self
            .state
            .text
            .as_ref()
            .and_then(|bank| bank.by_selector(selector))
        else {
            return value.to_owned();
        };
        value
            .replace('&', &record.citation)
            .replace('|', &record.verse)
    }

    fn refresh_palette(&mut self) {
        for color in 0..256 {
            let adjustment = self.scene.palette_adjustments[color];
            let source = usize::from(self.scene.palette_mapping[color]);
            for component in 0..3 {
                let index = color * 3 + component;
                self.scene.palette.components[index] =
                    (i16::from(self.scene.base_palette.components[source * 3 + component])
                        + adjustment)
                        .clamp(0, 63) as u8;
            }
        }
    }

    fn next_random(&mut self) {
        self.rng ^= self.rng << 13;
        self.rng ^= self.rng >> 7;
        self.rng ^= self.rng << 17;
    }
}

impl Scene {
    fn animation_render_fields(&self, index: usize) -> Option<(&AnimationStep, i16, i16, u16)> {
        let mut visiting = vec![false; self.animations.len()];
        let (x, y, scale) = self.animation_transform(index, &mut visiting)?;
        let animation = self.animations.get(index)?;
        let step = animation.steps.get(animation.current)?;
        Some((step, x, y, scale))
    }

    fn animation_transform(&self, index: usize, visiting: &mut [bool]) -> Option<(i16, i16, u16)> {
        let animation = self.animations.get(index)?;
        if animation.state == 0 || animation.steps.is_empty() || *visiting.get(index)? {
            return None;
        }
        visiting[index] = true;
        let current = animation.steps.get(animation.current)?;
        let result = if let Some(parent) = animation.linked {
            let (parent_x, parent_y, parent_scale) = self.animation_transform(parent, visiting)?;
            let first = animation.steps.first()?;
            (
                parent_x.wrapping_add(current.x.wrapping_sub(first.x)),
                parent_y.wrapping_add(current.y.wrapping_sub(first.y)),
                parent_scale.wrapping_add(current.scale.wrapping_sub(first.scale)),
            )
        } else {
            (current.x, current.y, current.scale)
        };
        visiting[index] = false;
        Some(result)
    }
}

fn ensure_actor(actors: &mut Vec<SceneActor>, index: usize) {
    if actors.len() <= index {
        actors.resize_with(index + 1, SceneActor::default);
    }
}
fn ensure_navigation_node(
    nodes: &mut Vec<Option<NavigationNode>>,
    index: usize,
    value: NavigationNode,
) {
    if nodes.len() <= index {
        nodes.resize(index + 1, None);
    }
    nodes[index] = Some(value);
}
fn find_route(edges: &[(u8, u8)], start: u8, destination: u8) -> Option<Vec<RouteEdge>> {
    if start == destination {
        return Some(Vec::new());
    }
    let mut queue = VecDeque::from([start]);
    let mut parent: HashMap<u8, (u8, usize)> = HashMap::new();
    parent.insert(start, (start, usize::MAX));
    while let Some(node) = queue.pop_front() {
        for (index, &(left, right)) in edges.iter().enumerate() {
            let next = if left == node {
                Some(right)
            } else if right == node {
                Some(left)
            } else {
                None
            };
            if let Some(next) = next
                && !parent.contains_key(&next)
            {
                parent.insert(next, (node, index));
                if next == destination {
                    break;
                }
                queue.push_back(next);
            }
        }
        if parent.contains_key(&destination) {
            break;
        }
    }
    if !parent.contains_key(&destination) {
        return None;
    }
    let mut reverse = Vec::new();
    let mut node = destination;
    while node != start {
        let (from, index) = parent[&node];
        reverse.push(RouteEdge {
            index,
            from,
            to: node,
        });
        node = from;
    }
    reverse.reverse();
    Some(reverse)
}
/// The DOS timer interrupt runs at approximately 120 Hz and contributes 24
/// controller units per interrupt: 2,880 logical units per second.
const REFERENCE_TIMER_UNITS_PER_SECOND: u64 = 2_880;
const MILLISECONDS_PER_SECOND: u64 = 1_000;
const MAX_REFERENCE_TIMER_DELTA: u64 = 400;
const MOVEMENT_STEP_UNITS: u32 = 20;
const RUN_PHASE_INCREMENT: u16 = 28;
const RUN_PHASE_PERIOD: u16 = 0x600;
const RUN_FRAME_MAP: [u8; 36] = [
    1, 2, 3, 4, 5, 6, 19, 19, 19, 19, 19, 19, 7, 8, 9, 10, 11, 12, 20, 20, 20, 20, 20, 20, 13, 14,
    15, 16, 17, 18, 21, 21, 21, 21, 21, 21,
];

/// Converts a host millisecond clock into the timer units consumed by the
/// original controllers while retaining the fractional unit between frames.
#[derive(Default)]
pub(crate) struct ReferenceTimer {
    remainder: u64,
}

impl ReferenceTimer {
    pub(crate) fn advance_milliseconds(&mut self, elapsed_ms: u64) -> usize {
        let scaled = elapsed_ms
            .saturating_mul(REFERENCE_TIMER_UNITS_PER_SECOND)
            .saturating_add(self.remainder);
        self.remainder = scaled % MILLISECONDS_PER_SECOND;
        (scaled / MILLISECONDS_PER_SECOND).min(MAX_REFERENCE_TIMER_DELTA) as usize
    }
}

fn movement_duration(
    start_x: i16,
    start_y: i16,
    start_scale: u16,
    end_x: i16,
    end_y: i16,
    end_scale: u16,
) -> u32 {
    let dx = i32::from(end_x) - i32::from(start_x);
    let dy = i32::from(end_y) - i32::from(start_y);
    let scale_delta = i32::from(end_scale) - i32::from(start_scale);
    let major = dx.unsigned_abs().max(dy.unsigned_abs());
    let minor = dx.unsigned_abs().min(dy.unsigned_abs());
    let average_scale = (u32::from(start_scale) + u32::from(end_scale)) / 2;
    let planar = (major + minor / 2) * average_scale / 0x100;
    let depth = scale_delta.unsigned_abs();
    (planar.max(depth) + planar.min(depth) / 2).max(1)
}
fn lerp_i16(start: i16, end: i16, elapsed: u32, duration: u32) -> i16 {
    let start = i64::from(start);
    (start + (i64::from(end) - start) * i64::from(elapsed) / i64::from(duration)) as i16
}
fn lerp_u16(start: u16, end: u16, elapsed: u32, duration: u32) -> u16 {
    let start = i64::from(start);
    (start + (i64::from(end) - start) * i64::from(elapsed) / i64::from(duration)) as u16
}
fn prepare_actor_for_edge(actor: &mut SceneActor, end_x: i16, end_scale: u16) {
    let dx = i32::from(end_x) - i32::from(actor.x);
    let scale_delta = i32::from(end_scale) - i32::from(actor.scale);
    let average_scale = (u32::from(actor.scale) + u32::from(end_scale)) / 2;
    let scaled_x = dx.unsigned_abs() * average_scale / 0x100;
    actor.direction = if scale_delta.unsigned_abs() * 2 > scaled_x {
        if scale_delta >= 0 { 2 } else { 3 }
    } else if dx > 0 {
        1
    } else {
        0
    };
    set_actor_render_state(actor, true);
}
fn set_actor_render_state(actor: &mut SceneActor, moving: bool) {
    let direction_offset = match actor.direction & 3 {
        0 | 1 => 0,
        2 => 24,
        _ => 12,
    };
    let idle_offset = usize::from(!moving) * 6;
    let phase = usize::from(actor.animation_phase >> 8) % 6;
    actor.frame = RUN_FRAME_MAP[direction_offset + idle_offset + phase];
    actor.art_slot = 0;
    actor.flags = u8::from(actor.direction & 3 == 0);
}
fn resource_name(name: &str, extension: &str) -> String {
    if name.rsplit_once('.').is_some() {
        name.to_owned()
    } else {
        format!("{name}.{extension}")
    }
}
fn display_frame(object: &DisplayObject) -> u8 {
    if let DisplaySource::Direct { frame, .. } = object.source {
        frame
    } else {
        0
    }
}
fn set_display_frame(object: &mut DisplayObject, value: u8) {
    if let DisplaySource::Direct { frame, .. } = &mut object.source {
        *frame = value;
    }
}

#[cfg(test)]
mod animation_tests {
    use super::*;

    #[test]
    fn host_clock_matches_reference_timer_rate_and_cap() {
        let mut timer = ReferenceTimer::default();
        let units: usize = (0..100).map(|_| timer.advance_milliseconds(10)).sum();
        assert_eq!(units, 2_880);

        let mut stalled_timer = ReferenceTimer::default();
        assert_eq!(stalled_timer.advance_milliseconds(1_000), 400);
    }

    #[test]
    fn hole1_uses_silent_audio_fallback_instead_of_driver_loop() {
        let data_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../CB");
        if !data_dir.join("DD1.DAT").is_file() {
            return;
        }

        let config = LaunchConfig::parse(std::iter::empty::<&str>(), &data_dir).unwrap();
        let mut engine = Engine::open(config).unwrap();
        let program = engine.archive.read("HOLE1.BIN").unwrap();
        engine.scene = Scene::new("HOLE1".into(), program);
        for thread in &mut engine.scene.threads {
            thread.active = false;
        }

        let thread = &mut engine.scene.threads[2];
        thread.active = true;
        thread.ip = 0x01ea;
        engine.run_threads().unwrap();

        assert_eq!(engine.scene.threads[2].ip, 0x01f3);
        assert!(!engine.scene.threads[2].active);
    }

    #[test]
    fn silent_sound_wait_delays_only_the_calling_thread() {
        let data_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../CB");
        if !data_dir.join("DD1.DAT").is_file() {
            return;
        }

        let config = LaunchConfig::parse(std::iter::empty::<&str>(), &data_dir).unwrap();
        let mut engine = Engine::open(config).unwrap();
        engine.scene = Scene::new("SOUND-WAIT".into(), vec![0x59, 0x05]);
        engine.scene.threads[1].active = true;
        engine.scene.threads[1].ip = 1;
        engine.run_threads().unwrap();

        assert_eq!(engine.scene.threads[0].ip, 1);
        assert_eq!(engine.scene.threads[0].delay, -100);
        assert!(engine.scene.threads[0].active);
        assert!(!engine.scene.threads[1].active);
    }

    fn animation(mode: u8) -> Animation {
        let mut value = Animation::new(1);
        value.steps = (0..3)
            .map(|frame| AnimationStep {
                frame,
                art_slot: 0,
                x: 0,
                y: 0,
                scale: 0x100,
                flags: 0,
            })
            .collect();
        value.start(mode, None).unwrap();
        value
    }
    fn advance(value: &mut Animation) {
        value.countdown = 1;
        value.advance();
    }
    #[test]
    fn mode_one_finishes_after_last_step() {
        let mut a = animation(1);
        advance(&mut a);
        advance(&mut a);
        advance(&mut a);
        assert_eq!(a.state, 0);
    }
    #[test]
    fn modes_seven_and_eight_ping_pong() {
        let mut a = animation(7);
        advance(&mut a);
        advance(&mut a);
        advance(&mut a);
        assert_eq!((a.state, a.current), (8, 1));
        advance(&mut a);
        advance(&mut a);
        assert_eq!((a.state, a.current), (7, 1));
    }
    #[test]
    fn modes_nine_and_ten_reach_terminal_states() {
        let mut a = animation(9);
        advance(&mut a);
        advance(&mut a);
        advance(&mut a);
        assert_eq!(a.state, 6);
        let mut b = animation(10);
        advance(&mut b);
        advance(&mut b);
        advance(&mut b);
        assert_eq!(b.state, 5);
    }

    #[test]
    fn linked_animation_applies_delta_from_first_step() {
        let mut parent = animation(5);
        parent.steps[0].x = 100;
        parent.steps[0].y = 80;
        parent.steps[0].scale = 0x180;
        let mut child = animation(5);
        child.steps[0].x = 10;
        child.steps[0].y = 20;
        child.steps[0].scale = 0x100;
        child.steps[1].x = 14;
        child.steps[1].y = 17;
        child.steps[1].scale = 0x120;
        child.current = 1;
        child.linked = Some(0);
        let mut scene = Scene::new("TEST".into(), vec![]);
        scene.animations = vec![parent, child];
        let (_, x, y, scale) = scene.animation_render_fields(1).unwrap();
        assert_eq!((x, y, scale), (104, 77, 0x1a0));
        scene.animations[0].state = 0;
        assert!(scene.animation_render_fields(1).is_none());
    }

    #[test]
    fn route_retains_edge_indices_and_direction() {
        let edges = [(4, 2), (1, 2), (4, 7), (7, 9)];
        assert_eq!(
            find_route(&edges, 1, 9).unwrap(),
            vec![
                RouteEdge {
                    index: 1,
                    from: 1,
                    to: 2,
                },
                RouteEdge {
                    index: 0,
                    from: 2,
                    to: 4,
                },
                RouteEdge {
                    index: 2,
                    from: 4,
                    to: 7,
                },
                RouteEdge {
                    index: 3,
                    from: 7,
                    to: 9,
                },
            ]
        );
        assert!(find_route(&edges, 1, 6).is_none());
    }

    #[test]
    fn logo_edge_uses_reference_movement_length() {
        assert_eq!(movement_duration(6, 36, 0x200, 152, 30, 0x200), 298);
    }

    #[test]
    fn run_art_state_selects_direction_and_phase_frames() {
        let mut actor = SceneActor {
            x: 6,
            y: 36,
            scale: 0x200,
            ..SceneActor::default()
        };
        prepare_actor_for_edge(&mut actor, 152, 0x200);
        assert_eq!((actor.direction, actor.frame, actor.flags), (1, 1, 0));
        actor.animation_phase = 0x100;
        set_actor_render_state(&mut actor, true);
        assert_eq!(actor.frame, 2);
        set_actor_render_state(&mut actor, false);
        assert_eq!(actor.frame, 19);
    }
}
