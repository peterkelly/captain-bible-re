use std::process::Command;

fn main() {
    let output = Command::new("pkg-config")
        .args(["--libs", "sdl3"])
        .output()
        .expect("building Captain Bible requires pkg-config and SDL3");
    if !output.status.success() {
        panic!("building Captain Bible requires the SDL3 development package");
    }
    let flags = String::from_utf8(output.stdout).expect("pkg-config emitted non-UTF-8 flags");
    for flag in flags.split_whitespace() {
        if let Some(path) = flag.strip_prefix("-L") {
            println!("cargo:rustc-link-search=native={path}");
        } else if let Some(library) = flag.strip_prefix("-l") {
            println!("cargo:rustc-link-lib=dylib={library}");
        } else if let Some(path) = flag.strip_prefix("-Wl,-rpath,") {
            println!("cargo:rustc-link-arg=-Wl,-rpath,{path}");
        }
    }
}
