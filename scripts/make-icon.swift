import AppKit

// Génère l'icône source (PNG carré). Dégradé cyan→magenta de la marque RANDROID,
// éclair blanc (thème flash). Usage : swift make-icon.swift sortie.png [taille]
let args = CommandLine.arguments
guard args.count >= 2 else { FileHandle.standardError.write("usage: make-icon.swift out.png [size]\n".data(using: .utf8)!); exit(2) }
let out = args[1]
let size = args.count >= 3 ? (Int(args[2]) ?? 1024) : 1024
let s = CGFloat(size)

let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size,
    bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
    colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)

// Fond : coin arrondi + dégradé diagonal
let inset = s * 0.06
let rect = NSRect(x: inset, y: inset, width: s - 2*inset, height: s - 2*inset)
let path = NSBezierPath(roundedRect: rect, xRadius: s*0.22, yRadius: s*0.22)
let grad = NSGradient(colors: [
    NSColor(calibratedRed: 0.10, green: 0.80, blue: 0.95, alpha: 1),
    NSColor(calibratedRed: 0.72, green: 0.25, blue: 0.95, alpha: 1)])!
grad.draw(in: path, angle: -45)

// Éclair blanc centré
let b = NSBezierPath()
func pt(_ x: CGFloat, _ y: CGFloat) -> NSPoint { NSPoint(x: s*x, y: s*y) }
b.move(to: pt(0.56, 0.80))
b.line(to: pt(0.36, 0.48))
b.line(to: pt(0.49, 0.48))
b.line(to: pt(0.44, 0.20))
b.line(to: pt(0.64, 0.54))
b.line(to: pt(0.51, 0.54))
b.close()
NSColor.white.setFill()
b.fill()

NSGraphicsContext.restoreGraphicsState()
guard let data = rep.representation(using: .png, properties: [:]) else { exit(1) }
try! data.write(to: URL(fileURLWithPath: out))
