# Buktahula Home Assistant Add-ons

Offizielles Home Assistant Add-on Repository für Buktahula Add-ons.

[![Open your Home Assistant instance and show the add-on store with a specific repository enabled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fbuktahula%2Fhassio-addons)

---

## 📦 Enthaltene Add-ons

* **[LG ESS Solar](LG_ESS/)**: Python/Docker-Dienst für LG ESS Solar-Wechselrichter & Batteriespeicher zur automatischen Integration in Home Assistant via MQTT.

---

## 🚀 Installation & Einbindung in Home Assistant

> [!NOTE]
> **Wichtiger Hinweis zum Unterschied zwischen Add-ons und HACS:**  
> Home Assistant Add-ons sind eigenständige Docker-Container und werden über den **Home Assistant Add-on Store** (Supervisor) verwaltet, **nicht** über HACS!  
> (HACS verwaltet ausschließlich Frontend-Karten/Dashboards und Integrationen, jedoch keine Docker-Add-ons.)

### 1-Klick-Installation (My Home Assistant)
Klicke einfach auf den blauen Button oben oder nutze diesen Link:  
👉 [Repository zu Home Assistant hinzufügen](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fbuktahula%2Fhassio-addons)

### Manuelle Einbindung im Add-on Store:
1. Öffne Home Assistant und navigiere zu **Einstellungen** ➔ **Add-ons**.
2. Klicke unten rechts auf **Add-on Store**.
3. Klicke oben rechts auf das Drei-Punkte-Menü (`⋮`) ➔ **Repositories**.
4. Füge folgende URL ein und klicke auf **Hinzufügen**:
   ```
   https://github.com/buktahula/hassio-addons
   ```
5. Nach dem Schließen des Dialogs findest du das Add-on **LG ESS Solar** in der Liste des Stores und kannst es mit einem Klick installieren.

---

## 🎨 Passende Lovelace Dashboard Card

Für die Visualisierung im Dashboard gibt es die maßgeschneiderte Lovelace-Karte:
* ☀️ **[LG ESS Solar Card](https://github.com/buktahula/lg-ess-card)**  
  *(Diese Karte kann direkt über **HACS** als benutzerdefiniertes Dashboard-Repository installiert werden!)*
