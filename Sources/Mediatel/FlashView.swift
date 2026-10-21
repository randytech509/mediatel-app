import SwiftUI

// Flash de firmware — outils LÉGITIMES uniquement (Heimdall open source, Odin4
// protocole Samsung). Aucun contournement de verrou/FRP : un flash réécrit des
// partitions signées, il ne saute aucune sécurité. Chaque écriture est confirmée.
struct FlashView: View {
    @EnvironmentObject var model: AppModel
    @Environment(\.dismiss) private var dismiss

    @State private var hasHeimdall = false
    @State private var hasOdin4 = false
    @State private var busy = false
    @State private var log = "Prêt."

    // Odin4 : archives Samsung .tar.md5
    @State private var bl = ""
    @State private var ap = ""
    @State private var cp = ""
    @State private var csc = ""
    // Heimdall : partition -> image .img
    @State private var parts: [PartRow] = [PartRow()]

    struct PartRow: Identifiable { let id = UUID(); var name = ""; var file = "" }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Flash de firmware", systemImage: "bolt.fill").font(.title2.bold())
                Spacer()
                Button("Fermer") { dismiss() }
            }
            Text("Restaure un firmware signé. Aucun contournement de compte ou de verrou FRP.")
                .font(.caption).foregroundStyle(.secondary)

            HStack(spacing: 16) {
                toolBadge("Heimdall", hasHeimdall)
                toolBadge("Odin4", hasOdin4)
                Spacer()
            }

            Divider()
            steps
            Divider()

            if hasOdin4 { odinSection }
            if hasHeimdall { heimdallSection }
            if !hasHeimdall && !hasOdin4 { installHint }

            Divider()
            ScrollView { Text(log).font(.system(.caption, design: .monospaced))
                .frame(maxWidth: .infinity, alignment: .leading) }
                .frame(height: 90)
            if busy { ProgressView().controlSize(.small) }
        }
        .padding(18)
        .frame(width: 640)
        .onAppear {
            Task {
                let h = await Task.detached { Shell.which("heimdall") }.value
                let o = await Task.detached { Shell.which("odin4") }.value
                hasHeimdall = h; hasOdin4 = o
            }
        }
    }

    private func toolBadge(_ name: String, _ ok: Bool) -> some View {
        HStack(spacing: 4) {
            Image(systemName: ok ? "checkmark.circle.fill" : "xmark.circle")
                .foregroundStyle(ok ? .green : .secondary)
            Text(name).font(.callout)
        }
    }

    private var steps: some View {
        HStack {
            Button { rebootDownload() } label: { Label("Passer en mode Download", systemImage: "arrow.down.to.line") }
                .disabled(model.current?.state != "device")
            Button { detect() } label: { Label("Détecter (Download)", systemImage: "magnifyingglass") }
            Spacer()
        }
    }

    // ----- Odin4 -----
    private var odinSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Odin4 — archives Samsung (.tar.md5)").font(.headline)
            fileRow("BL  (bootloader)", $bl)
            fileRow("AP  (système)", $ap)
            fileRow("CP  (modem)", $cp)
            fileRow("CSC (région)", $csc)
            Text("Un firmware inadapté peut briquer l'appareil — le modèle doit correspondre exactement.")
                .font(.caption).foregroundStyle(.orange)
            Button { flashOdin() } label: { Label("Flasher avec Odin4", systemImage: "bolt.fill") }
                .disabled(busy || [bl, ap, cp, csc].allSatisfy { $0.isEmpty })
        }
    }

    private func fileRow(_ label: String, _ bind: Binding<String>) -> some View {
        HStack {
            Text(label).font(.system(.body, design: .monospaced)).frame(width: 140, alignment: .leading)
            Text(bind.wrappedValue.isEmpty ? "—" : URL(fileURLWithPath: bind.wrappedValue).lastPathComponent)
                .font(.caption).foregroundStyle(.secondary).lineLimit(1).truncationMode(.head)
            Spacer()
            Button("Choisir") { if let f = Panels.chooseFirmware() { bind.wrappedValue = f } }
            if !bind.wrappedValue.isEmpty {
                Button { bind.wrappedValue = "" } label: { Image(systemName: "xmark.circle") }.buttonStyle(.borderless)
            }
        }
    }

    // ----- Heimdall -----
    private var heimdallSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Heimdall — images de partition (.img)").font(.headline)
            Text("Extrais d'abord les archives (tar → .img ; décompresse les .lz4).")
                .font(.caption).foregroundStyle(.secondary)
            ForEach($parts) { $row in
                HStack {
                    TextField("PARTITION (ex : RECOVERY)", text: $row.name).frame(width: 190)
                    Text(row.file.isEmpty ? "—" : URL(fileURLWithPath: row.file).lastPathComponent)
                        .font(.caption).foregroundStyle(.secondary).lineLimit(1).truncationMode(.head)
                    Spacer()
                    Button("Choisir") { if let f = Panels.chooseFirmware() { row.file = f } }
                }
            }
            HStack {
                Button { parts.append(PartRow()) } label: { Label("Ajouter", systemImage: "plus") }
                Spacer()
                Button { flashHeimdall() } label: { Label("Flasher avec Heimdall", systemImage: "bolt.fill") }
                    .disabled(busy || !parts.contains { !$0.name.isEmpty && !$0.file.isEmpty })
            }
        }
    }

    private var installHint: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Aucun outil de flash installé.").foregroundStyle(.orange)
            Text("Heimdall (open source) : brew install heimdall").font(.caption)
            Text("Odin4 (CLI Samsung) : place le binaire 'odin4' dans le PATH.").font(.caption)
        }
    }

    // ----- Actions -----
    private func rebootDownload() {
        guard let dev = model.current else { return }
        run("Envoi de reboot download…", ["adb", "-s", dev.id, "reboot", "download"])
    }

    private func detect() {
        busy = true; log = "Détection…"
        Task {
            var found = false; var out = ""
            if hasHeimdall {
                let r = await Task.detached { Shell.run(["heimdall", "detect"]) }.value
                found = found || r.code == 0; out += r.out + r.err
            }
            if hasOdin4 {
                let r = await Task.detached { Shell.run(["odin4", "-l"]) }.value
                found = found || (r.code == 0 && !r.out.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                out += r.out
            }
            log = found ? "Appareil détecté en mode Download." : "Aucun appareil en mode Download.\n\(out)"
            busy = false
        }
    }

    private func flashOdin() {
        var args = ["odin4"]
        if !bl.isEmpty { args += ["-b", bl] }
        if !ap.isEmpty { args += ["-a", ap] }
        if !cp.isEmpty { args += ["-c", cp] }
        if !csc.isEmpty { args += ["-s", csc] }
        run("Flash Odin4 en cours…", args)
    }

    private func flashHeimdall() {
        var args = ["heimdall", "flash", "--no-reboot"]
        for row in parts where !row.name.isEmpty && !row.file.isEmpty {
            args += ["--" + row.name.uppercased(), row.file]
        }
        run("Flash Heimdall en cours…", args)
    }

    private func run(_ starting: String, _ args: [String]) {
        busy = true; log = starting
        Task {
            let r = await Task.detached { Shell.run(args) }.value
            log = (r.code == 0 ? "OK.\n" : "Échec (code \(r.code)).\n") + r.out + r.err
            busy = false
        }
    }
}
