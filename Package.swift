// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Mediatel",
    platforms: [.macOS(.v14)],
    targets: [
        // Mode langage v5 : évite la concurrence stricte de Swift 6 sur une UI
        // qui appelle des Process bloquants. Suffisant et stable ici.
        .executableTarget(
            name: "Mediatel",
            path: "Sources/Mediatel",
            swiftSettings: [.swiftLanguageMode(.v5)]
        )
    ]
)
