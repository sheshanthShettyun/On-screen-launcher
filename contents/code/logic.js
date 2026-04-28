.pragma library

var apps = []
var history = []

function fallbackApps() {
    return [
        { name: "System Settings", subtitle: "Configure Plasma and system preferences", desktopFile: "systemsettings.desktop", icon: "preferences-system", section: "Top Results" },
        { name: "Dolphin", subtitle: "Browse files and folders", desktopFile: "org.kde.dolphin.desktop", icon: "system-file-manager", section: "Top Results" },
        { name: "Konsole", subtitle: "Terminal emulator", desktopFile: "org.kde.konsole.desktop", icon: "utilities-terminal", section: "Top Results" },
        { name: "Firefox", subtitle: "Web browser", desktopFile: "firefox.desktop", icon: "firefox", section: "Top Results" },
        { name: "KWrite", subtitle: "Text editor", desktopFile: "org.kde.kwrite.desktop", icon: "accessories-text-editor", section: "Recent" },
        { name: "Discover", subtitle: "Install and update software", desktopFile: "org.kde.discover.desktop", icon: "plasmadiscover", section: "Recent" },
        { name: "Spectacle", subtitle: "Screenshot and screen recording", desktopFile: "org.kde.spectacle.desktop", icon: "spectacle", section: "Recent" },
        { name: "Kate", subtitle: "Advanced text editor", desktopFile: "org.kde.kate.desktop", icon: "kate", section: "Recent" }
    ]
}

function normalizeApp(app) {
    var name = String(app.name || app.display || app.title || "").trim()
    if (!name) {
        return null
    }

    var desktopFile = String(app.desktopFile || app.storageId || app.exec || app.id || "").trim()
    if (!desktopFile) {
        desktopFile = name.toLowerCase().replace(/\s+/g, "-") + ".desktop"
    }
    if (desktopFile.indexOf(".desktop") === -1 && desktopFile.indexOf("/") === -1) {
        desktopFile += ".desktop"
    }

    return {
        name: name,
        subtitle: String(app.subtitle || app.description || app.comment || desktopFile),
        desktopFile: desktopFile,
        icon: String(app.icon || app.decoration || app.iconName || "application-x-executable"),
        section: app.section || "Top Results"
    }
}

function loadApps(externalApps) {
    var nextApps = []
    var source = externalApps && externalApps.length ? externalApps : fallbackApps()
    var seen = {}

    for (var i = 0; i < source.length; i++) {
        var app = normalizeApp(source[i])
        if (!app || seen[app.desktopFile]) {
            continue
        }
        seen[app.desktopFile] = true
        nextApps.push(app)
    }

    apps = nextApps
    return apps
}

function loadHistory(plasmoidObject) {
    try {
        var raw = plasmoidObject ? plasmoidObject.readConfig("history") : "[]"
        var parsed = JSON.parse(raw || "[]")
        history = parsed instanceof Array ? parsed : []
    } catch (e) {
        history = []
    }
    return history
}

function saveHistory(plasmoidObject) {
    if (plasmoidObject) {
        plasmoidObject.writeConfig("history", JSON.stringify(history.slice(0, 20)))
    }
}

function updateHistory(app, plasmoidObject) {
    var key = app && app.desktopFile ? app.desktopFile : String(app || "")
    if (!key) {
        return history
    }

    var existing = null
    var next = []
    for (var i = 0; i < history.length; i++) {
        if (history[i].desktopFile === key || history[i].name === key) {
            existing = history[i]
        } else {
            next.push(history[i])
        }
    }

    next.unshift({
        name: app.name || key,
        desktopFile: key,
        count: existing ? Number(existing.count || 1) + 1 : 1,
        lastUsed: Date.now()
    })

    history = next.slice(0, 20)
    saveHistory(plasmoidObject)
    return history
}

function historyEntry(app) {
    var key = app.desktopFile || app.name
    for (var i = 0; i < history.length; i++) {
        if (history[i].desktopFile === key || history[i].name === app.name) {
            return history[i]
        }
    }
    return null
}

function scoreApp(app, query) {
    var q = query.toLowerCase().trim()
    var name = app.name.toLowerCase()
    var subtitle = String(app.subtitle || "").toLowerCase()
    var desktopFile = String(app.desktopFile || "").toLowerCase()
    var h = historyEntry(app)
    var score = 0

    if (!q) {
        score += 10
    } else if (name.indexOf(q) === 0) {
        score += 120
    } else if (desktopFile.indexOf(q) === 0) {
        score += 90
    } else if (name.indexOf(q) !== -1) {
        score += 70
    } else if (subtitle.indexOf(q) !== -1 || desktopFile.indexOf(q) !== -1) {
        score += 35
    } else {
        return -1
    }

    if (h) {
        score += Math.min(Number(h.count || 1) * 8, 56)
        score += Math.max(0, 20 - history.indexOf(h))
    }

    score += Math.max(0, 20 - name.length) / 10
    return score
}

function search(query) {
    var ranked = []

    for (var i = 0; i < apps.length; i++) {
        var score = scoreApp(apps[i], String(query || ""))
        if (score >= 0) {
            ranked.push({ app: apps[i], score: score })
        }
    }

    ranked.sort(function(a, b) {
        if (b.score !== a.score) {
            return b.score - a.score
        }
        return a.app.name.localeCompare(b.app.name)
    })

    var results = []
    for (var j = 0; j < ranked.length && j < 12; j++) {
        var item = ranked[j].app
        item.section = j < 5 ? "Top Results" : "Recent"
        results.push(item)
    }
    return results
}
