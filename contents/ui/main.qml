import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import org.kde.plasma.core 2.0 as PlasmaCore
import org.kde.plasma.plasmoid 2.0
import org.kde.plasma.private.kicker 0.1 as Kicker

import "../code/logic.js" as Logic

    Item {
    id: root

    width: 1
    height: 1
    Layout.minimumWidth: 1
    Layout.maximumWidth: 1
    Layout.minimumHeight: 1
    Layout.maximumHeight: 1

    property int selectedIndex: 0
    property var activeModel: runnerModel.count > 0 ? runnerModel.modelForRow(0) : null
    property string uiFont: "JetBrains Mono"

    Plasmoid.preferredRepresentation: Plasmoid.compactRepresentation
    Plasmoid.compactRepresentation: compactButton
    Plasmoid.icon: "search"
    Plasmoid.status: PlasmaCore.Types.ActiveStatus
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.onActivated: plasmoid.expanded = !plasmoid.expanded

    function resetLauncher() {
        searchField.text = ""
        selectedIndex = 0
        runnerModel.query = ""
        searchField.forceActiveFocus()
    }

    function launchFromModel(sourceModel, row) {
        if (!sourceModel || row < 0 || row >= sourceModel.count) {
            return
        }

        var modelIndex = sourceModel.index(row, 0)
        var title = String(sourceModel.data(modelIndex, Qt.DisplayRole) || "")
        if (title.length > 0) {
            Logic.updateHistory({ name: title, desktopFile: title }, plasmoid)
        }

        if (sourceModel.trigger && sourceModel.trigger(row, "", null)) {
            plasmoid.expanded = false
            resetLauncher()
        }
    }

    function launchSelected() {
        if (searchField.text.length > 0 && root.activeModel && root.activeModel.count > 0) {
            launchFromModel(root.activeModel, selectedIndex)
        }
    }

    Component.onCompleted: {
        Logic.loadHistory(plasmoid)
        if (plasmoid.hasOwnProperty("activationTogglesExpanded")) {
            plasmoid.activationTogglesExpanded = true
        }
        plasmoid.hideOnWindowDeactivate = true
    }

    Connections {
        target: plasmoid
        function onExpandedChanged(expanded) {
            if (expanded) {
                resetLauncher()
            }
        }
    }

    Kicker.RunnerModel {
        id: runnerModel
        appletInterface: plasmoid
        runners: ["services", "krunner_systemsettings", "calculator", "unitconverter"]
        deleteWhenEmpty: false
    }

    Component {
        id: compactButton

        Item {
            width: 1
            height: 1

            Rectangle {
                anchors.fill: parent
                color: "transparent"
            }

            PlasmaCore.IconItem {
                visible: false
                width: 1
                height: 1
                source: "search"
            }

            MouseArea {
                id: mouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: plasmoid.expanded = !plasmoid.expanded
            }
        }
    }

    PlasmaCore.Dialog {
        id: launcherDialog

        visible: plasmoid.expanded
        type: PlasmaCore.Dialog.PopupMenu
        flags: Qt.WindowStaysOnTopHint
        hideOnWindowDeactivate: true

        function positionDialog() {
            if (!visible || !plasmoid || !plasmoid.screenGeometry) {
                return
            }

            var screenX = plasmoid.screenGeometry.x
            var screenY = plasmoid.screenGeometry.y
            var screenW = plasmoid.screenGeometry.width
            var screenH = plasmoid.screenGeometry.height
            var visualOffset = 36
            x = screenX + Math.round((screenW - width) / 2)
            y = screenY + Math.round((screenH - height) / 2) + visualOffset
        }

        onVisibleChanged: {
            if (visible) {
                positionDialog()
                searchField.forceActiveFocus()
            }
        }
        onWidthChanged: positionDialog()
        onHeightChanged: positionDialog()

        mainItem: FocusScope {
            id: popup

            width: 520
            height: 585
            Layout.minimumWidth: 520
            Layout.maximumWidth: 520
            Layout.minimumHeight: 585
            Layout.maximumHeight: 585
            focus: true

            Keys.onPressed: function(event) {
                if (event.key === Qt.Key_Escape) {
                    plasmoid.expanded = false
                    event.accepted = true
                }
            }

            Rectangle {
                id: shell

                anchors.fill: parent
                radius: 4
                color: "#242424"
                border.width: 1
                border.color: "#303030"
                clip: true
                antialiasing: true

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 12

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 60
                        radius: 8
                        color: "#303030"
                        border.width: 1
                        border.color: searchField.activeFocus ? "#505050" : "#444444"
                        antialiasing: true

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 18
                            anchors.rightMargin: 14
                            spacing: 12

                            PlasmaCore.IconItem {
                                Layout.preferredWidth: 22
                                Layout.preferredHeight: 22
                                source: "search"
                                active: searchField.activeFocus
                                opacity: 0.78
                            }

                            TextField {
                                id: searchField

                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                placeholderText: "Search apps, commands, settings..."
                                color: "#f4f4f4"
                                placeholderTextColor: "#8e8e8e"
                                selectedTextColor: "#ffffff"
                                selectionColor: "#555555"
                                font.family: root.uiFont
                                font.pixelSize: 18
                                leftPadding: 0
                                rightPadding: 0
                                topPadding: 0
                                bottomPadding: 0
                                verticalAlignment: TextInput.AlignVCenter
                                background: Item {}

                                onTextChanged: {
                                    runnerModel.query = text
                                    root.selectedIndex = 0
                                }

                                Keys.onPressed: function(event) {
                                    var currentCount = searchField.text.length > 0 && root.activeModel ? root.activeModel.count : 0

                                    if (event.key === Qt.Key_Down) {
                                        root.selectedIndex = Math.min(root.selectedIndex + 1, Math.max(0, currentCount - 1))
                                        resultsView.currentIndex = root.selectedIndex
                                        event.accepted = true
                                    } else if (event.key === Qt.Key_Up) {
                                        root.selectedIndex = Math.max(root.selectedIndex - 1, 0)
                                        resultsView.currentIndex = root.selectedIndex
                                        event.accepted = true
                                    } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                        launchSelected()
                                        event.accepted = true
                                    } else if (event.key === Qt.Key_Escape) {
                                        plasmoid.expanded = false
                                        event.accepted = true
                                    }
                                }
                            }

                            PlasmaCore.IconItem {
                                Layout.preferredWidth: 19
                                Layout.preferredHeight: 19
                                source: "drive-harddisk"
                                opacity: 0.62
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: searchField.text.length > 0 ? "Top results" : "Launcher"
                        color: "#d4d4d4"
                        font.family: root.uiFont
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }

                    ListView {
                        id: resultsView

                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: searchField.text.length > 0
                        model: root.activeModel
                        clip: true
                        spacing: 4
                        currentIndex: root.selectedIndex
                        boundsBehavior: Flickable.StopAtBounds

                        delegate: resultDelegate

                        Text {
                            anchors.centerIn: parent
                            visible: searchField.text.length > 0 && (!root.activeModel || root.activeModel.count === 0)
                            text: "No results"
                            color: "#8a8a8a"
                            font.pixelSize: 14
                        }
                    }

                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: searchField.text.length === 0

                        ColumnLayout {
                            anchors.centerIn: parent
                            width: parent.width
                            spacing: 12

                            PlasmaCore.IconItem {
                                Layout.alignment: Qt.AlignHCenter
                                Layout.preferredWidth: 44
                                Layout.preferredHeight: 44
                                source: "start-here-kde"
                                opacity: 0.72
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Start typing to search desktop apps"
                                color: "#e6e6e6"
                                font.family: root.uiFont
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                                horizontalAlignment: Text.AlignHCenter
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Applications, settings, commands, and runner results"
                                color: "#8f8f8f"
                                font.family: root.uiFont
                                font.pixelSize: 11
                                horizontalAlignment: Text.AlignHCenter
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 1
                        color: "#3a3a3a"
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 18
                        spacing: 8

                        KeyHint { label: "↑↓"; text: "Navigate" }
                        KeyHint { label: "↵"; text: "Open" }
                        Item { Layout.fillWidth: true }
                    }
                }
            }

            Component.onCompleted: searchField.forceActiveFocus()
        }
    }

    Component {
        id: resultDelegate

        Item {
            id: row

            width: ListView.view.width
            height: 50

            property bool selected: ListView.isCurrentItem
            property bool hovered: itemMouse.containsMouse
            property var sourceModel: ListView.view.model
            property var sourceIndex: sourceModel ? sourceModel.index(index, 0) : null
            property string title: sourceModel ? String(sourceModel.data(sourceIndex, Qt.DisplayRole) || "") : ""
            property string subtitle: sourceModel ? String(sourceModel.data(sourceIndex, Qt.ToolTipRole) || sourceModel.data(sourceIndex, Qt.UserRole + 2) || "") : ""
            property var iconSource: sourceModel ? sourceModel.data(sourceIndex, Qt.DecorationRole) : "application-x-executable"

            Rectangle {
                anchors.fill: parent
                radius: 7
                color: row.selected ? "#343434" : row.hovered ? "#2f2f2f" : "transparent"
                Behavior on color { ColorAnimation { duration: 110 } }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 10

                PlasmaCore.IconItem {
                    Layout.preferredWidth: 26
                    Layout.preferredHeight: 26
                    source: row.iconSource || "application-x-executable"
                    active: row.selected || row.hovered
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1

                    Text {
                        Layout.fillWidth: true
                        text: row.title
                        color: "#ffffff"
                        font.family: root.uiFont
                        font.pixelSize: 13
                        font.weight: row.selected ? Font.DemiBold : Font.Normal
                        elide: Text.ElideRight
                    }

                    Text {
                        Layout.fillWidth: true
                        text: row.subtitle
                        color: "#a5a5a5"
                        visible: text.length > 0
                        font.family: root.uiFont
                        font.pixelSize: 11
                        elide: Text.ElideRight
                    }
                }

                Text {
                    text: "×"
                    visible: !row.selected
                    color: "#a0a0a0"
                    opacity: row.hovered ? 0.9 : 0.55
                    font.family: root.uiFont
                    font.pixelSize: 18
                }

                Text {
                    text: "↵"
                    visible: row.selected
                    color: "#cfcfcf"
                    font.family: root.uiFont
                    font.pixelSize: 14
                }
            }

            MouseArea {
                id: itemMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onEntered: {
                    root.selectedIndex = index
                    row.ListView.view.currentIndex = index
                }
                onClicked: launchFromModel(row.sourceModel, index)
            }
        }
    }

    component KeyHint: RowLayout {
        property string label
        property string text

        spacing: 5

        Rectangle {
            Layout.preferredWidth: Math.max(26, hintText.implicitWidth + 10)
            Layout.preferredHeight: 17
            radius: 4
            color: "#343434"

            Text {
                id: hintText
                anchors.centerIn: parent
                text: label
                color: "#b8b8b8"
                font.family: root.uiFont
                font.pixelSize: 10
            }
        }

        Text {
            text: parent.text
            color: "#a3a3a3"
            font.family: root.uiFont
            font.pixelSize: 11
        }
    }
}
