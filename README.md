# Störungsauskunft für Home Assistant

Strom-, Gas-, Wasser- und Fernwärmestörungen von [störungsauskunft.de](https://xn--strungsauskunft-9sb.de/) als Sensoren in Home Assistant – für das ganze Saarland oder für frei wählbare Postleitzahlen.

> **Inoffiziell.** Die Integration nutzt die nicht dokumentierte Schnittstelle hinter dem Web-Frontend von störungsauskunft.de. Sie steht in keiner Verbindung zum Betreiber und kann jederzeit nicht mehr funktionieren, wenn sich die Website ändert. Bitte das Abrufintervall nicht unter 5 Minuten setzen.

## Was sie liefert

Pro gewählter Sparte (Strom, Gas, Wasser, Fernwärme) entstehen drei Entitäten:

| Entität | Zustand | Attribute |
|---|---|---|
| `binary_sensor.…_strom_storung` | **an**, wenn eine offizielle Störung läuft **oder** eine auffällige Häufung von Bürgermeldungen | `official`, `suspected`, `official_postal_codes`, `suspected_postal_codes` |
| `sensor.…_strom_offizielle_storungen` | Anzahl offizieller Störungen der Netzbetreiber | `outages` (PLZ, Ort, Ortsteil, Netzbetreiber, Beginn, voraussichtliches Ende), `planned` (angekündigte Abschaltungen) |
| `sensor.…_strom_burgermeldungen` | Anzahl Bürgermeldungen in laufenden Häufungen | `areas` (PLZ, Ort, Netzbetreiber, Meldungen, Adressen, seit, letzte, `suspected`, `confirmed`) |

**Häufung = möglicher Ausfall:** Standardmäßig gilt eine PLZ als auffällig, wenn innerhalb von 30 Minuten mindestens 8 Meldungen von mindestens 5 verschiedenen Adressen eingehen. Kommt 120 Minuten lang keine neue Meldung, ist die Häufung vorbei. Alle Werte lassen sich in den Optionen ändern.

## Datenschutz

Bürgermeldungen enthalten bei störungsauskunft.de Straße, Hausnummer und Freitext. Diese Felder werden nur intern zum Zählen eindeutiger Adressen benutzt und landen **nie** in Home Assistant – weder in Zuständen noch in Attributen oder Ereignissen. Die Listen-Attribute werden außerdem nicht im Recorder gespeichert.

## Installation

1. HACS → ⋮ → **Benutzerdefinierte Repositories** → `https://github.com/Saarlandpower/ha-stoerungsauskunft`, Kategorie **Integration**
2. „Störungsauskunft“ installieren und Home Assistant neu starten
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Störungsauskunft**

Manuell: den Ordner `custom_components/stoerungsauskunft` nach `config/custom_components/` kopieren und neu starten.

## Einrichtung

- **Gebiet:** „Ganzes Saarland“ (alle saarländischen PLZ) oder „Eigene PLZ“
- **Postleitzahlen:** durch Komma getrennt. Weniger als 5 Ziffern gelten als Präfix, z. B. `664` für alle PLZ ab 664.
- **Sparten:** Strom, Gas, Wasser, Fernwärme

Für mehrere Gebiete einfach mehrere Einträge anlegen, z. B. „Saarland“ für den Überblick und ein zweiter nur mit der eigenen PLZ für Benachrichtigungen.

## Ereignisse für Automationen

| Ereignis | Wann |
|---|---|
| `stoerungsauskunft_outage_new` | neue offizielle Störung im Gebiet |
| `stoerungsauskunft_outage_resolved` | offizielle Störung verschwunden |
| `stoerungsauskunft_suspected` | neue auffällige Häufung von Bürgermeldungen |

Die Ereignisdaten enthalten `sector` (`strom`, `gas`, `wasser`, `fernwaerme`), `postal_code`, `city`, `operator` und die Zeiten. Beim Start von Home Assistant wird nur der aktuelle Stand gemerkt, es gibt also keine Ereignisflut nach einem Neustart.

```yaml
automation:
  - alias: Stromausfall in der Nähe
    triggers:
      - trigger: event
        event_type: stoerungsauskunft_outage_new
        event_data:
          sector: strom
    actions:
      - action: notify.mobile_app_handy
        data:
          title: "⚡ Stromausfall {{ trigger.event.data.postal_code }} {{ trigger.event.data.city }}"
          message: >-
            {{ trigger.event.data.operator or 'Netzbetreiber unbekannt' }},
            seit {{ as_datetime(trigger.event.data.start).strftime('%H:%M') }}
            {%- if trigger.event.data.end %}, Ende vsl. {{ as_datetime(trigger.event.data.end).strftime('%H:%M') }}{% endif %}
```

## Entwicklung

```bash
pip install pytest-homeassistant-custom-component
pytest -q
```

Lizenz: MIT
