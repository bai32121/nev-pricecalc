import UIKit
import WebKit

/// 单页面容器：用 WKWebView 加载打进包里的 index.html。
///
/// 页面是零外部依赖的单文件（CSS/JS 全内联、图标是 base64），
/// 所以用 file:// 直接加载即可完全离线运行，不需要网络权限。
/// 用 file:// 而不是 loadHTMLString 的原因：页面里有 location.reload()
/// （"恢复默认"按钮），file:// 能重新读文件，假 URL 会 404。
final class RootViewController: UIViewController {

    private var webView: WKWebView!
    /// 与网页 --bg 变量同色（#f5f6f8），刘海和底部留白才不违和
    private let pageBackground = UIColor(red: 0.9608, green: 0.9647, blue: 0.9725, alpha: 1.0)

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = pageBackground
        setupWebView()
        observeKeyboard()
        loadPage()
    }

    override var preferredStatusBarStyle: UIStatusBarStyle {
        return .darkContent
    }

    // MARK: - 视图

    private func setupWebView() {
        let config = WKWebViewConfiguration()
        // 持久化存储：保存的购车方案（localStorage）跨启动保留
        config.websiteDataStore = .default()
        config.allowsInlineMediaPlayback = true
        if #available(iOS 14.0, *) {
            config.defaultWebpagePreferences.allowsContentJavaScript = true
        }

        webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        webView.translatesAutoresizingMaskIntoConstraints = false
        webView.isOpaque = false
        webView.backgroundColor = .clear
        webView.scrollView.backgroundColor = .clear
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.scrollView.keyboardDismissMode = .interactive
        webView.allowsBackForwardNavigationGestures = false
        view.addSubview(webView)

        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            webView.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor)
        ])
    }

    // MARK: - 加载

    private func loadPage() {
        guard let url = Bundle.main.url(forResource: "index", withExtension: "html") else {
            showError("内置页面缺失\n\n打包时 index.html 没有进到 app 里，请重新构建。")
            return
        }
        webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
    }

    private func showError(_ text: String) {
        let label = UILabel()
        label.numberOfLines = 0
        label.font = .systemFont(ofSize: 15)
        label.textColor = UIColor(white: 0.25, alpha: 1)
        label.textAlignment = .center
        label.text = text
        label.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(label)
        NSLayoutConstraint.activate([
            label.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            label.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            label.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 32),
            label.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -32)
        ])
    }

    // MARK: - 键盘

    /// 页面底部有输入框（首付、选配金额），软键盘弹出时把 webView 内容往上让
    private func observeKeyboard() {
        let center = NotificationCenter.default
        center.addObserver(self, selector: #selector(keyboardWillChange(_:)),
                           name: UIResponder.keyboardWillChangeFrameNotification, object: nil)
        center.addObserver(self, selector: #selector(keyboardWillHide),
                           name: UIResponder.keyboardWillHideNotification, object: nil)
    }

    @objc private func keyboardWillChange(_ note: Notification) {
        guard let info = note.userInfo,
              let frame = (info[UIResponder.keyboardFrameEndUserInfoKey] as? NSValue)?.cgRectValue
        else { return }
        let converted = view.convert(frame, from: nil)
        let overlap = max(0, view.bounds.maxY - converted.minY)
        webView.scrollView.contentInset.bottom = overlap
        webView.scrollView.verticalScrollIndicatorInsets.bottom = overlap
    }

    @objc private func keyboardWillHide() {
        webView.scrollView.contentInset.bottom = 0
        webView.scrollView.verticalScrollIndicatorInsets.bottom = 0
    }
}

extension RootViewController: WKNavigationDelegate {

    func webView(_ webView: WKWebView,
                 didFailProvisionalNavigation navigation: WKNavigation!,
                 withError error: Error) {
        showError("页面加载失败\n\n\(error.localizedDescription)")
    }

    func webView(_ webView: WKWebView,
                 decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        // 只允许本地 file://，任何外链交给系统浏览器
        if let url = navigationAction.request.url,
           url.scheme != nil, url.scheme != "file", url.scheme != "about" {
            if UIApplication.shared.canOpenURL(url) {
                UIApplication.shared.open(url)
            }
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }
}
