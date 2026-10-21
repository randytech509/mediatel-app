import SwiftUI

struct ContentView: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        NavigationSplitView {
            sidebar.navigationSplitViewColumnWidth(min: 220, ideal: 250)
        } detail: {
            browser
        }
        .sheet(isPresented: $model.showFlash) { FlashView().environmentObject(model) }
    }

    // ----- Colonne appareils -----
    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Appareils").font(.headline)
                Spacer()
                Button { model.refreshDevices() } label: { Image(systemName: "arrow.clockwise") }
                    .buttonStyle(.borderless).help("Rafraîchir (adb devices)")
            }
            .padding(10)
            Divider()
            List(selection: $model.selected) {
                ForEach(model.devices) { d in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(d.model).fontWeight(.medium)
                        Text(d.id).font(.caption).foregroundStyle(.secondary)
                        stateBadge(d.state)
                    }
                    .tag(d.id)
                }
            }
            .onChange(of: model.selected) { _, _ in model.path = "/sdcard"; model.listPath() }
            if model.devices.isEmpty {
                Text("Branche un appareil Android, débogage USB activé.")
                    .font(.caption).foregroundStyle(.secondary).padding(10)
            }
        }
    }

    private func stateBadge(_ s: String) -> some View {
        let color: Color = s == "device" ? .green : (s == "unauthorized" ? .orange : .gray)
        return Text(s).font(.caption2).padding(.horizontal, 6).padding(.vertical, 1)
            .background(color.opacity(0.2)).foregroundStyle(color).clipShape(Capsule())
    }

    // ----- Explorateur -----
    private var browser: some View {
        VStack(spacing: 0) {
            toolbar
            Divider()
            pathBar
            Divider()
            if model.current?.state == "unauthorized" {
                notice("Appareil non autorisé : accepte « Autoriser le débogage USB » sur l'écran.")
            } else if model.current == nil {
                notice("Aucun appareil sélectionné.")
            } else {
                fileTable
            }
            Divider()
            statusBar
        }
    }

    private var toolbar: some View {
        HStack(spacing: 8) {
            Button { model.showFlash = true } label: { Label("Flash firmware", systemImage: "bolt.fill") }
            Divider().frame(height: 18)
            Button { if let f = Panels.chooseFile() { model.push(local: f) } } label: {
                Label("Copier depuis le PC", systemImage: "arrow.up.circle")
            }.disabled(model.current?.state != "device" || model.busy)
            Button { pullSelected() } label: { Label("Copier vers le PC", systemImage: "arrow.down.circle") }
                .disabled(model.selectedEntry == nil || model.busy)
            Button { newFolder() } label: { Label("Nouveau dossier", systemImage: "folder.badge.plus") }
                .disabled(model.current?.state != "device" || model.busy)
            Button { model.listPath() } label: { Image(systemName: "arrow.clockwise") }
                .help("Rafraîchir la liste").disabled(model.current?.state != "device")
            Spacer()
            if let p = model.progress {
                ProgressView(value: p).frame(width: 120)
                Text("\(Int(p * 100)) %").font(.caption).monospacedDigit()
            } else if model.busy {
                ProgressView().controlSize(.small)
            }
        }
        .padding(8)
    }

    private var pathBar: some View {
        HStack(spacing: 8) {
            Button { model.goUp() } label: { Image(systemName: "arrow.up") }
                .disabled(model.path == "/").help("Dossier parent")
            Image(systemName: "folder")
            Text(model.path).font(.system(.body, design: .monospaced)).lineLimit(1).truncationMode(.head)
            Spacer()
        }
        .padding(.horizontal, 10).padding(.vertical, 6)
    }

    private var fileTable: some View {
        Table(model.entries, selection: $model.selectedEntry) {
            TableColumn("Nom") { e in
                HStack {
                    Image(systemName: e.isDir ? "folder.fill" : "doc")
                        .foregroundStyle(e.isDir ? Color.accentColor : .secondary)
                    Text(e.name)
                }
            }
            TableColumn("Taille") { e in
                Text(e.isDir ? "—" : humanSize(e.size)).foregroundStyle(.secondary)
            }.width(90)
            TableColumn("Modifié") { e in
                Text(e.date).font(.caption).foregroundStyle(.secondary)
            }.width(130)
        }
        .contextMenu(forSelectionType: FileEntry.ID.self) { ids in
            if let e = entry(ids) {
                Button { copyToPC(e) } label: { Label("Copier vers le PC…", systemImage: "arrow.down.circle") }
                if e.isDir {
                    Button { model.open(e) } label: { Label("Ouvrir", systemImage: "folder") }
                }
                Button { renameEntry(e) } label: { Label("Renommer…", systemImage: "pencil") }
                Divider()
                Button(role: .destructive) { deleteEntry(e) } label: {
                    Label("Supprimer", systemImage: "trash")
                }
            }
        } primaryAction: { ids in
            if let e = entry(ids), e.isDir { model.open(e) }
        }
    }

    private func notice(_ t: String) -> some View {
        VStack { Spacer(); Text(t).foregroundStyle(.secondary).multilineTextAlignment(.center).padding(); Spacer() }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var statusBar: some View {
        HStack {
            Text(model.status).font(.caption).foregroundStyle(.secondary)
            Spacer()
            Text("RANDROID · RandyTech Solutions").font(.caption2).foregroundStyle(.tertiary)
        }
        .padding(.horizontal, 10).padding(.vertical, 5)
    }

    // ----- Actions -----
    private func entry(_ ids: Set<FileEntry.ID>) -> FileEntry? {
        guard let id = ids.first else { return nil }
        return model.entries.first { $0.id == id }
    }

    private func pullSelected() {
        guard let id = model.selectedEntry,
              let e = model.entries.first(where: { $0.id == id }) else { return }
        copyToPC(e)
    }

    private func copyToPC(_ e: FileEntry) {
        if let dir = Panels.chooseDir() { model.pull(entry: e, toDir: dir) }
    }

    private func renameEntry(_ e: FileEntry) {
        if let n = Panels.prompt("Renommer « \(e.name) »", defaultValue: e.name) {
            model.rename(e, to: n)
        }
    }

    private func deleteEntry(_ e: FileEntry) {
        if Panels.confirmDelete(e.name) { model.delete(e) }
    }

    private func newFolder() {
        if let n = Panels.prompt("Nom du nouveau dossier") { model.makeDir(n) }
    }
}
