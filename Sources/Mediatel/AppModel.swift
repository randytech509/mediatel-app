import SwiftUI
import Foundation

struct Device: Identifiable, Hashable, Sendable {
    let id: String        // numéro de série adb
    let model: String
    let platform: String  // "android"
    let state: String     // device | unauthorized | offline
}

struct FileEntry: Identifiable, Hashable, Sendable {
    var id: String { name }
    let name: String
    let isDir: Bool
    let size: Int64
    let date: String
}

@MainActor
final class AppModel: ObservableObject {
    @Published var devices: [Device] = []
    @Published var selected: String?
    @Published var path: String = "/sdcard"
    @Published var entries: [FileEntry] = []
    @Published var selectedEntry: FileEntry.ID?
    @Published var status: String = "Prêt."
    @Published var busy: Bool = false
    @Published var progress: Double? = nil   // transfert en cours : 0…1
    @Published var showFlash: Bool = false

    var current: Device? { devices.first { $0.id == selected } }

    func joinPath(_ name: String) -> String {
        (path.hasSuffix("/") ? path : path + "/") + name
    }

    // ----- Appareils -----
    func refreshDevices() {
        busy = true
        Task {
            let r = await Task.detached { Shell.run(["adb", "devices", "-l"]) }.value
            var list: [Device] = []
            for line in r.out.split(separator: "\n").dropFirst() {
                let parts = line.split(whereSeparator: { $0 == " " || $0 == "\t" })
                    .map(String.init).filter { !$0.isEmpty }
                guard let serial = parts.first else { continue }
                let state = parts.count > 1 ? parts[1] : "?"
                var mdl = "?"
                for tok in parts where tok.hasPrefix("model:") { mdl = String(tok.dropFirst(6)) }
                list.append(Device(id: serial, model: mdl, platform: "android", state: state))
            }
            self.devices = list
            if self.selected == nil || !list.contains(where: { $0.id == self.selected }) {
                self.selected = list.first?.id
            }
            self.status = list.isEmpty ? "Aucun appareil détecté (adb)." : "\(list.count) appareil(s)."
            self.busy = false
            if self.current?.state == "device" { self.listPath() } else { self.entries = [] }
        }
    }

    // ----- Explorateur -----
    func listPath() {
        guard let dev = current, dev.state == "device" else { entries = []; return }
        let serial = dev.id
        let p = shQuote(path.hasSuffix("/") ? path : path + "/")
        busy = true
        Task {
            let r = await Task.detached {
                Shell.run(["adb", "-s", serial, "shell", "ls -AlL --color=never \(p) 2>/dev/null"])
            }.value
            self.entries = Self.parseLs(r.out)
            self.selectedEntry = nil
            self.busy = false
        }
    }

    func open(_ e: FileEntry) {
        guard e.isDir else { return }
        path = (path.hasSuffix("/") ? String(path.dropLast()) : path) + "/" + e.name
        listPath()
    }

    func goUp() {
        guard path != "/" else { return }
        let trimmed = path.hasSuffix("/") ? String(path.dropLast()) : path
        if let idx = trimmed.lastIndex(of: "/") {
            let parent = String(trimmed[..<idx])
            path = parent.isEmpty ? "/" : parent
        }
        listPath()
    }

    // ----- Transferts (progression par taille) -----
    // adb masque le pourcentage « [ x%] » quand la sortie n'est pas un TTY.
    // On mesure donc l'avancement en sondant la taille de la destination.

    // Copier DEPUIS le PC vers l'appareil.
    func push(local: String) {
        guard let dev = current else { return }
        let serial = dev.id, dest = path
        let base = URL(fileURLWithPath: local).lastPathComponent
        let total = localSizeOf(local)                    // 0 si dossier/inconnu
        let destPath = (dest.hasSuffix("/") ? dest : dest + "/") + base
        busy = true; progress = total > 0 ? 0 : nil
        status = "Copie vers l'appareil : \(base)…"
        Task {
            let poller: Task<Void, Never>? = total > 0 ? Task {
                while !Task.isCancelled {
                    try? await Task.sleep(nanoseconds: 350_000_000)
                    let s = await self.remoteSize(serial, destPath)
                    if !Task.isCancelled { self.progress = min(1, Double(s) / Double(total)) }
                }
            } : nil
            let res = await Task.detached {
                Shell.run(["adb", "-s", serial, "push", local, dest + "/"])
            }.value
            poller?.cancel()
            self.progress = nil; self.busy = false
            self.status = res.code == 0
                ? "Copié vers l'appareil\(total > 0 ? " (\(humanSize(total)))" : "")."
                : "Échec de la copie."
            self.listPath()
        }
    }

    // Copier VERS le PC depuis l'appareil.
    func pull(entry: FileEntry, toDir dir: String) {
        guard let dev = current else { return }
        let serial = dev.id
        let remote = joinPath(entry.name)
        let total = entry.size                            // connu par ls (0 si dossier)
        let localDest = (dir.hasSuffix("/") ? dir : dir + "/") + entry.name
        busy = true; progress = total > 0 ? 0 : nil
        status = "Copie vers le PC : \(entry.name)…"
        Task {
            let poller: Task<Void, Never>? = total > 0 ? Task {
                while !Task.isCancelled {
                    try? await Task.sleep(nanoseconds: 350_000_000)
                    let s = self.localFileSize(localDest)
                    if !Task.isCancelled { self.progress = min(1, Double(s) / Double(total)) }
                }
            } : nil
            let res = await Task.detached {
                Shell.run(["adb", "-s", serial, "pull", remote, dir])
            }.value
            poller?.cancel()
            self.progress = nil; self.busy = false
            self.status = res.code == 0 ? "Copié dans \(dir)." : "Échec de la copie."
        }
    }

    // Taille d'un fichier/dossier sur l'appareil (octets).
    func remoteSize(_ serial: String, _ p: String) async -> Int64 {
        let r = await Task.detached {
            Shell.run(["adb", "-s", serial, "shell", "stat -c %s \(shQuote(p)) 2>/dev/null"])
        }.value
        return Int64(r.out.trimmingCharacters(in: .whitespacesAndNewlines)) ?? 0
    }

    // Taille locale : fichier seul (les dossiers renvoient 0 -> progression indéterminée).
    func localSizeOf(_ path: String) -> Int64 {
        let fm = FileManager.default
        var isDir: ObjCBool = false
        guard fm.fileExists(atPath: path, isDirectory: &isDir), !isDir.boolValue else { return 0 }
        let attrs = try? fm.attributesOfItem(atPath: path)
        return (attrs?[.size] as? NSNumber)?.int64Value ?? 0
    }

    func localFileSize(_ path: String) -> Int64 {
        let attrs = try? FileManager.default.attributesOfItem(atPath: path)
        return (attrs?[.size] as? NSNumber)?.int64Value ?? 0
    }

    // ----- Opérations fichier (menu contextuel) -----
    func delete(_ e: FileEntry) {
        guard let dev = current else { return }
        let serial = dev.id, target = joinPath(e.name)
        busy = true; status = "Suppression…"
        Task {
            let r = await Task.detached {
                Shell.run(["adb", "-s", serial, "shell", "rm -rf \(shQuote(target))"])
            }.value
            self.status = r.code == 0 ? "Supprimé." : "Échec de la suppression."
            self.busy = false
            self.listPath()
        }
    }

    func rename(_ e: FileEntry, to newName: String) {
        guard let dev = current, !newName.isEmpty else { return }
        let serial = dev.id, src = joinPath(e.name), dst = joinPath(newName)
        busy = true; status = "Renommage…"
        Task {
            let r = await Task.detached {
                Shell.run(["adb", "-s", serial, "shell", "mv \(shQuote(src)) \(shQuote(dst))"])
            }.value
            self.status = r.code == 0 ? "Renommé." : "Échec du renommage."
            self.busy = false
            self.listPath()
        }
    }

    func makeDir(_ name: String) {
        guard let dev = current, !name.isEmpty else { return }
        let serial = dev.id, target = joinPath(name)
        busy = true; status = "Création du dossier…"
        Task {
            let r = await Task.detached {
                Shell.run(["adb", "-s", serial, "shell", "mkdir -p \(shQuote(target))"])
            }.value
            self.status = r.code == 0 ? "Dossier créé." : "Échec de la création."
            self.busy = false
            self.listPath()
        }
    }

    // ----- Analyse de `ls -AlL` -----
    static func parseLs(_ out: String) -> [FileEntry] {
        var res: [FileEntry] = []
        for raw in out.split(separator: "\n", omittingEmptySubsequences: false) {
            let line = String(raw).trimmingCharacters(in: CharacterSet(charactersIn: "\r"))
            if line.isEmpty || line.hasPrefix("total ") { continue }
            let cols = splitFields(line, max: 8)
            if cols.count < 8 { continue }
            let perm = cols[0]
            let size = cols[4]
            var name = cols[7]
            let isDir = perm.hasPrefix("d")
            let isLink = perm.hasPrefix("l")
            if isLink, let r = name.range(of: " -> ") { name = String(name[..<r.lowerBound]) }
            res.append(FileEntry(
                name: name, isDir: isDir || isLink,
                size: (isDir || isLink) ? 0 : (Int64(size) ?? 0),
                date: "\(cols[5]) \(cols[6])"
            ))
        }
        return res.sorted {
            ($0.isDir ? 0 : 1, $0.name.lowercased()) < ($1.isDir ? 0 : 1, $1.name.lowercased())
        }
    }

    static func splitFields(_ s: String, max: Int) -> [String] {
        var fields: [String] = []
        var rest = Substring(s)
        while fields.count < max - 1 {
            while rest.first == " " { rest = rest.dropFirst() }
            guard let sp = rest.firstIndex(of: " ") else { break }
            fields.append(String(rest[..<sp]))
            rest = rest[sp...]
        }
        while rest.first == " " { rest = rest.dropFirst() }
        if !rest.isEmpty { fields.append(String(rest)) }
        return fields
    }
}

func humanSize(_ n: Int64) -> String {
    var v = Double(n)
    for u in ["o", "Ko", "Mo", "Go", "To"] {
        if v < 1024 { return u == "o" ? "\(Int(v))\(u)" : String(format: "%.1f%@", v, u) }
        v /= 1024
    }
    return String(format: "%.1fPo", v)
}
