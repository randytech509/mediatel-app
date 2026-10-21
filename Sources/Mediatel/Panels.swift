import AppKit

// Dialogues natifs (AppKit). Appelés depuis des actions de vue = thread principal.
enum Panels {
    static func chooseFile() -> String? {
        let p = NSOpenPanel()
        p.canChooseFiles = true; p.canChooseDirectories = false; p.allowsMultipleSelection = false
        return p.runModal() == .OK ? p.url?.path : nil
    }

    static func chooseFirmware() -> String? {
        let p = NSOpenPanel()
        p.canChooseFiles = true; p.canChooseDirectories = false; p.allowsMultipleSelection = false
        p.title = "Choisir un fichier firmware"
        return p.runModal() == .OK ? p.url?.path : nil
    }

    static func chooseDir() -> String? {
        let p = NSOpenPanel()
        p.canChooseFiles = false; p.canChooseDirectories = true; p.allowsMultipleSelection = false
        p.prompt = "Copier ici"
        return p.runModal() == .OK ? p.url?.path : nil
    }

    // Saisie d'une ligne (nouveau dossier, renommer).
    static func prompt(_ title: String, defaultValue: String = "") -> String? {
        let a = NSAlert()
        a.messageText = title
        a.addButton(withTitle: "OK")
        a.addButton(withTitle: "Annuler")
        let tf = NSTextField(frame: NSRect(x: 0, y: 0, width: 260, height: 24))
        tf.stringValue = defaultValue
        a.accessoryView = tf
        a.window.initialFirstResponder = tf
        let r = a.runModal()
        let v = tf.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        return (r == .alertFirstButtonReturn && !v.isEmpty) ? v : nil
    }

    // Confirmation d'une action destructive.
    static func confirmDelete(_ name: String) -> Bool {
        let a = NSAlert()
        a.messageText = "Supprimer « \(name) » ?"
        a.informativeText = "Suppression définitive sur l'appareil. Irréversible."
        a.alertStyle = .warning
        a.addButton(withTitle: "Supprimer")
        a.addButton(withTitle: "Annuler")
        return a.runModal() == .alertFirstButtonReturn
    }
}
