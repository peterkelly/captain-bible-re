//! A clean-room, original-data-compatible Captain Bible engine core.
//!
//! The engine core uses only the Rust standard library. Host frontends can
//! drive [`Engine`] with logical input events and display its 320x200 indexed
//! framebuffer; the crate requires SDL3 for its graphical frontend.

pub mod archive;
pub mod audio;
pub mod bytecode;
pub mod config;
pub mod engine;
pub mod error;
pub mod frontend;
pub mod graphics;
pub mod save;
pub mod state;
pub mod text;
pub mod world;

pub use engine::{Engine, EngineEvent, EngineStatus, InputEvent, StudyRecord};
pub use error::{EngineError, Result};
