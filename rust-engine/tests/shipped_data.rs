use captain_bible_engine::Engine;
use captain_bible_engine::archive::Archive;
use captain_bible_engine::bytecode::{code_regions, decode};
use captain_bible_engine::config::{InstallationPolicy, LaunchConfig};
use captain_bible_engine::graphics::SCREEN_PIXELS;
use captain_bible_engine::text::{TextBank, export_study};
use std::collections::BTreeMap;
use std::fs;
use std::path::PathBuf;

fn data_directory() -> Option<PathBuf> {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../CB");
    path.join("DD1.DAT").is_file().then_some(path)
}

#[test]
fn shipped_archive_and_bytecode_conform() {
    let Some(data_directory) = data_directory() else {
        return;
    };
    let archive = Archive::open(data_directory.join("DD1.DAT")).unwrap();
    assert_eq!(archive.entries().len(), 369);
    let mut extensions = BTreeMap::new();
    for entry in archive.entries() {
        *extensions.entry(entry.extension.as_str()).or_insert(0usize) += 1;
        let data = archive.extract(entry).unwrap();
        if entry.extension == "BIN" {
            for region in code_regions(&entry.filename(), data.len()) {
                let mut position = region.start;
                while position < region.end {
                    position = decode(&data[..region.end], position).unwrap().end;
                }
                assert_eq!(position, region.end);
            }
        }
    }
    assert_eq!(extensions.get("ART"), Some(&143));
    assert_eq!(extensions.get("BIN"), Some(&62));
    assert_eq!(extensions.get("ABT"), Some(&41));
    assert_eq!(extensions.get("PAL"), Some(&37));
    assert_eq!(extensions.get(""), Some(&33));
    assert_eq!(extensions.get("XMI"), Some(&32));
    assert_eq!(extensions.get("MAP"), Some(&21));
}

#[test]
fn logo_scene_executes_and_renders_from_resources() {
    let Some(data_directory) = data_directory() else {
        return;
    };
    let config = LaunchConfig::parse(std::iter::empty::<&str>(), &data_directory).unwrap();
    let mut engine = Engine::open(config).unwrap();
    engine.tick([]).unwrap();
    assert_eq!(engine.scene_name(), "LOGO");
    assert_eq!(engine.framebuffer().pixels().len(), SCREEN_PIXELS);
    assert!(
        engine
            .framebuffer()
            .pixels()
            .iter()
            .any(|&pixel| pixel != 0)
    );
}

#[test]
fn logo_reflection_and_running_actor_regression() {
    let Some(data_directory) = data_directory() else {
        return;
    };
    let config = LaunchConfig::parse(std::iter::empty::<&str>(), &data_directory).unwrap();
    let mut first = Engine::open(config.clone()).unwrap();
    let mut second = Engine::open(config.clone()).unwrap();
    first.tick_elapsed([], 4_000).unwrap();
    second.tick_elapsed([], 4_200).unwrap();

    let pixels = first.framebuffer().pixels();
    let clear = pixels[0];
    let reflected_sky = pixels[40 * 320 + 40];
    let normal_sky = pixels[40 * 320 + 265];
    assert_ne!(reflected_sky, clear);
    assert_eq!(reflected_sky, normal_sky);
    assert_ne!(first.framebuffer(), second.framebuffer());

    let mut entering = Engine::open(config).unwrap();
    entering.tick_elapsed([], 1_000).unwrap();
    let pixels = entering.framebuffer().pixels();
    // The actor overlaps this coordinate, but the later left-dome record
    // must restore the black oval matte over it.
    assert_eq!(pixels[50 * 320 + 10], pixels[0]);
}

#[test]
fn study_export_matches_qemu_capture() {
    let Some(data_directory) = data_directory() else {
        return;
    };
    let archive = Archive::open(data_directory.join("DD1.DAT")).unwrap();
    let policy =
        InstallationPolicy::parse(&fs::read(data_directory.join("SOUND.5")).unwrap()).unwrap();
    let mut config = LaunchConfig::parse(["-g63", "-sTignored"], &data_directory).unwrap();
    config.apply_policy(policy);
    let translation = captain_bible_engine::config::translation_letter(
        config.export.as_ref().unwrap().translation,
    )
    .unwrap();
    let banks: Vec<_> = b"ABCDEFGR"
        .iter()
        .map(|&bank| {
            TextBank::parse(
                bank,
                &archive
                    .read(&format!("{translation}{}", bank as char))
                    .unwrap(),
                &fs::read(data_directory.join(format!("DDL{}", bank as char))).unwrap(),
                false,
            )
            .unwrap()
        })
        .collect();
    let output = export_study(&banks, 63, config.filter_mature).unwrap();
    let hash = output.iter().fold(0xcbf2_9ce4_8422_2325u64, |hash, &byte| {
        (hash ^ u64::from(byte)).wrapping_mul(0x100_0000_01b3)
    });
    assert_eq!(output.len(), 132_510);
    assert_eq!(hash, 0xa2d5_a397_c556_77ab);
}

#[test]
fn normal_save_slot_round_trips_checkpoint_state() {
    let Some(data_directory) = data_directory() else {
        return;
    };
    let nonce = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let prefix = std::env::temp_dir().join(format!(
        "captain-bible-rust-save-test-{}-{nonce}",
        std::process::id(),
    ));
    let argument = prefix.to_string_lossy().into_owned();
    let config = LaunchConfig::parse([argument], &data_directory).unwrap();
    let mut engine = Engine::open(config).unwrap();
    engine.state.variables[21] = 4_321;
    engine.state.snapshot();
    engine.save_slot(3, "Rust test").unwrap();
    assert_eq!(engine.save_index().unwrap().labels[2], "Rust test");
    engine.state.variables[21] = 0;
    engine.load_slot(3).unwrap();
    assert_eq!(engine.state.variables[21], 4_321);

    let _ = fs::remove_file(format!("{}.SV0", prefix.display()));
    let _ = fs::remove_file(format!("{}.SV3", prefix.display()));
}
