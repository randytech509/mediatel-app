import Foundation

struct ShellResult: Sendable {
    let code: Int32
    let out: String
    let err: String
}

// Exécution de binaires externes (adb, heimdall, odin4).
//
// PATH : une app lancée depuis le Finder hérite d'un PATH minimal sans Homebrew
// ni platform-tools Android. On le reconstruit avant chaque appel.
enum Shell {
    static let extraPaths: [String] = [
        "/opt/homebrew/bin", "/opt/homebrew/sbin",
        "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin",
        NSString(string: "~/Library/Android/sdk/platform-tools").expandingTildeInPath,
        NSString(string: "~/Android/Sdk/platform-tools").expandingTildeInPath,
    ]

    static func env() -> [String: String] {
        var e = ProcessInfo.processInfo.environment
        let current = (e["PATH"] ?? "").split(separator: ":").map(String.init)
        var seen = Set<String>()
        var merged: [String] = []
        for p in extraPaths + current where !p.isEmpty && seen.insert(p).inserted {
            merged.append(p)
        }
        e["PATH"] = merged.joined(separator: ":")
        return e
    }

    // Bloquant. Lit stdout ET stderr EN PARALLÈLE : sinon un stderr qui dépasse
    // 64 Ko avant la fin de stdout bloque le process (deadlock de pipe classique).
    static func run(_ args: [String]) -> ShellResult {
        guard let first = args.first else {
            return ShellResult(code: 1, out: "", err: "commande vide")
        }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        p.arguments = args
        p.environment = env()
        let outPipe = Pipe(), errPipe = Pipe()
        p.standardOutput = outPipe
        p.standardError = errPipe
        do {
            try p.run()
        } catch {
            return ShellResult(code: 127, out: "", err: "introuvable : \(first)")
        }
        var outData = Data(), errData = Data()
        let group = DispatchGroup()
        let q = DispatchQueue(label: "com.randytech.mediatel.shell", attributes: .concurrent)
        q.async(group: group) { outData = outPipe.fileHandleForReading.readDataToEndOfFile() }
        q.async(group: group) { errData = errPipe.fileHandleForReading.readDataToEndOfFile() }
        p.waitUntilExit()
        group.wait()
        return ShellResult(
            code: p.terminationStatus,
            out: String(data: outData, encoding: .utf8) ?? "",
            err: String(data: errData, encoding: .utf8) ?? ""
        )
    }

    static func which(_ bin: String) -> Bool { run(["which", bin]).code == 0 }
}

func shQuote(_ s: String) -> String { "'" + s.replacingOccurrences(of: "'", with: "'\\''") + "'" }
