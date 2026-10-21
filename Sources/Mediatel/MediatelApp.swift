import SwiftUI

@main
struct MediatelApp: App {
    @StateObject private var model = AppModel()

    var body: some Scene {
        WindowGroup("RANDROID — Mediatel") {
            ContentView()
                .environmentObject(model)
                .frame(minWidth: 860, minHeight: 540)
                .onAppear { model.refreshDevices() }
        }
        .windowResizability(.contentMinSize)
    }
}
