import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "kab.fusion360"
  manageIpc: false

  // The application launcher owns runtime, authentication, and process state.
  // This widget only reads its public report and dispatches a detached launch.
  property var status: null
  property string statusError: ""
  property bool statusTimedOut: false
  property string diagnosticText: ""
  property bool diagnosticTimedOut: false
  property bool diagnosticRequested: false
  property int cursorIndex: 0

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property bool canLaunch: status !== null
    && status.installed === true && status.runtime_ready === true
    && status.session_conflict !== true
  readonly property string statusText: {
    if (statusProcess.running) return "Checking installation…"
    if (statusError !== "") return statusError
    if (status === null) return "Open this panel to check Fusion."
    if (!status.installed) return "Fusion is not installed."
    if (status.session_conflict === true) return "Close the other Fusion session before opening this one."
    if (status.running) return "Fusion is running."
    if (!status.runtime_ready) return "Fusion needs attention before it can open."
    return "Fusion is installed."
  }
  readonly property string detailText: {
    if (status === null) return ""
    var lines = []
    if (status.fusion_version) lines.push("Version: " + String(status.fusion_version))
    if (Array.isArray(status.errors)) {
      for (var i = 0; i < status.errors.length; i++) lines.push(String(status.errors[i]))
    }
    return lines.join("\n")
  }

  implicitWidth: barButton.implicitWidth
  implicitHeight: barButton.implicitHeight

  onOpenedChanged: {
    if (opened) {
      cursorIndex = 0
      diagnosticText = ""
      scroller.contentY = 0
      refreshStatus()
    } else {
      diagnosticRequested = false
      diagnosticTimeout.stop()
      diagnosticProcess.running = false
    }
  }

  function refreshStatus() {
    if (statusProcess.running) return
    root.status = null
    root.statusError = ""
    root.statusTimedOut = false
    statusTimeout.restart()
    statusProcess.running = true
  }

  function applyStatus(output) {
    if (root.statusTimedOut) return
    try {
      var report = JSON.parse(output)
      if (report.schema_version !== 1
          || typeof report.installed !== "boolean"
          || typeof report.running !== "boolean"
          || typeof report.runtime_ready !== "boolean"
          || typeof report.session_attachment_ready !== "boolean") {
        throw new Error("Unsupported status report")
      }
      root.status = report
      root.statusError = ""
    } catch (error) {
      root.status = null
      root.statusError = "Status is unavailable. Check that the Fusion launcher is installed."
    }
  }

  function launchFusion() {
    if (!root.canLaunch) return
    Quickshell.execDetached(["fusion360-for-omarchy", "launch"])
    root.close()
  }

  function showDiagnostics() {
    if (diagnosticProcess.running) return
    root.diagnosticText = "Collecting diagnostics…"
    root.diagnosticTimedOut = false
    root.diagnosticRequested = true
    diagnosticTimeout.restart()
    diagnosticProcess.running = true
  }

  function activateCursor() {
    if (root.cursorIndex === 0) root.launchFusion()
    else if (root.cursorIndex === 1) root.refreshStatus()
    else root.showDiagnostics()
  }

  Process {
    id: statusProcess
    command: ["fusion360-for-omarchy", "status", "--json"]
    stdout: StdioCollector {
      id: statusOutput
      waitForEnd: true
      onStreamFinished: {
        statusTimeout.stop()
        root.applyStatus(statusOutput.text)
      }
    }
    // Do not forward external output into the long-running shell's journal.
    stderr: StdioCollector { waitForEnd: true }
  }

  Timer {
    id: statusTimeout
    interval: 8000
    onTriggered: {
      root.statusTimedOut = true
      statusProcess.running = false
      root.status = null
      root.statusError = "The Fusion launcher did not answer. Try Refresh or Diagnostics."
    }
  }

  Process {
    id: diagnosticProcess
    command: ["fusion360-for-omarchy", "diagnostics"]
    stdout: StdioCollector {
      id: diagnosticOutput
      waitForEnd: true
      onStreamFinished: {
        diagnosticTimeout.stop()
        if (root.diagnosticRequested && root.opened && !root.diagnosticTimedOut) {
          root.diagnosticRequested = false
          var report = diagnosticOutput.text.trim()
          root.diagnosticText = report
            ? report.slice(0, 12000) + (report.length > 12000 ? "\n[Report truncated]" : "")
            : "No diagnostic report was returned."
        }
      }
    }
    stderr: StdioCollector { waitForEnd: true }
  }

  Timer {
    id: diagnosticTimeout
    interval: 10000
    onTriggered: {
      if (!root.diagnosticRequested) return
      root.diagnosticRequested = false
      root.diagnosticTimedOut = true
      diagnosticProcess.running = false
      root.diagnosticText = "Diagnostics did not finish. Run fusion360-for-omarchy diagnostics in a terminal."
    }
  }

  WidgetButton {
    id: barButton
    anchors.fill: parent
    bar: root.bar
    text: barButton.vertical ? "F" : "Fusion"
    tooltipText: "Open Fusion 360 launcher and status"
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.LeftButton) root.toggle()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: barButton
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(390))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(580))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onMoveRequested: function(dx, dy) {
        root.cursorIndex = Math.max(0, Math.min(2, root.cursorIndex + dx + dy))
      }
      onActivateRequested: root.activateCursor()
      onTextKey: function(text) {
        if (text === "r" || text === "R") root.refreshStatus()
        else if (text === "d" || text === "D") root.showDiagnostics()
      }

      Flickable {
        id: scroller
        anchors.fill: parent
        contentWidth: width
        contentHeight: content.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        Controls.ScrollBar.vertical: Controls.ScrollBar {
          policy: Controls.ScrollBar.AsNeeded
        }

        Column {
          id: content
          width: scroller.width
          spacing: Style.space(10)

          Text {
            width: parent.width
            text: "Fusion 360"
            textFormat: Text.PlainText
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.subtitle
            font.bold: true
          }

          Text {
            width: parent.width
            text: root.statusText
            textFormat: Text.PlainText
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            wrapMode: Text.WordWrap
          }

          Text {
            width: parent.width
            visible: text !== ""
            text: root.detailText
            textFormat: Text.PlainText
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            wrapMode: Text.WordWrap
          }

          Button {
            width: parent.width
            text: "Open Fusion"
            enabled: root.canLaunch
            hasCursor: root.cursorIndex === 0
            bordered: true
            onHovered: function(isHovered) { if (isHovered) root.cursorIndex = 0 }
            onClicked: root.launchFusion()
          }

          Button {
            width: parent.width
            text: statusProcess.running ? "Checking…" : "Refresh status"
            enabled: !statusProcess.running
            hasCursor: root.cursorIndex === 1
            bordered: true
            onHovered: function(isHovered) { if (isHovered) root.cursorIndex = 1 }
            onClicked: root.refreshStatus()
          }

          Button {
            width: parent.width
            text: diagnosticProcess.running ? "Collecting…" : "Show diagnostics"
            enabled: !diagnosticProcess.running
            hasCursor: root.cursorIndex === 2
            bordered: true
            onHovered: function(isHovered) { if (isHovered) root.cursorIndex = 2 }
            onClicked: root.showDiagnostics()
          }

          Text {
            width: parent.width
            visible: text !== ""
            text: root.diagnosticText
            textFormat: Text.PlainText
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            wrapMode: Text.WrapAnywhere
          }
        }
      }
    }
  }
}
