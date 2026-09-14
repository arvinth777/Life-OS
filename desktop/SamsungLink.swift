import AppKit
import CoreServices

let appURL = Bundle.main.bundleURL
if CommandLine.arguments.contains("--register") {
    let old = LSCopyDefaultHandlerForURLScheme("ms-app" as CFString)?.takeRetainedValue() as String? ?? ""
    LSRegisterURL(appURL as CFURL, true)
    let result = LSSetDefaultHandlerForURLScheme("ms-app" as CFString, "local.lifeos.samsung-link" as CFString)
    print(old)
    exit(result == 0 ? 0 : 1)
}
if let index = CommandLine.arguments.firstIndex(of: "--restore"), CommandLine.arguments.count > index + 1 {
    let old = CommandLine.arguments[index + 1]
    if !old.isEmpty { LSSetDefaultHandlerForURLScheme("ms-app" as CFString, old as CFString) }
    exit(0)
}
class Delegate: NSObject, NSApplicationDelegate {
    func application(_ application: NSApplication, open urls: [URL]) {
        guard let url = urls.first,
              url.scheme == "ms-app",
              url.host == "s-1-15-2-4027708247-2189610-1983755848-2937435718-1578786913-2158692839-1974417358",
              let resource = Bundle.main.url(forResource: "session", withExtension: "json"),
              let data = try? Data(contentsOf: resource),
              let config = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let port = config["port"] as? Int, let nonce = config["nonce"] as? String,
              let target = URL(string: "http://127.0.0.1:\(port)/callback") else {
            NSApp.terminate(nil); return
        }
        var request = URLRequest(url: target)
        request.httpMethod = "POST"
        request.timeoutInterval = 60
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(nonce, forHTTPHeaderField: "X-Life-OS-Session")
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["callback": url.absoluteString])
        URLSession.shared.dataTask(with: request) { _, response, _ in
            DispatchQueue.main.async {
                let alert = NSAlert()
                let connected = (response as? HTTPURLResponse)?.statusCode == 200
                alert.messageText = connected ? "Samsung sign-in completed" : "Life OS could not finish the connection"
                alert.informativeText = connected ? "Return to Life OS to import your readings." : "Your sign-in reached Life OS, but the connection needs attention. Click OK and return to Life OS. Do not change your password or repeat sign-in yet."
                alert.runModal()
                NSApp.terminate(nil)
            }
        }.resume()
    }
}
let app = NSApplication.shared
let delegate = Delegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
