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

Eine Automation für alle drei Ereignisse und alle Sparten (Vorschlag von Ferdy Berger, leicht erweitert). Gerät in `notify.mobile_app_handy` anpassen; die Sparten in der Bedingung nach Bedarf kürzen.

```yaml
alias: "Notify: Störungsauskunft"
description: >-
  Neue und behobene offizielle Störungen sowie auffällige Häufungen von
  Bürgermeldungen (Strom, Gas, Wasser).
mode: parallel
max: 10
triggers:
  - trigger: event
    event_type: stoerungsauskunft_outage_new
    id: new
  - trigger: event
    event_type: stoerungsauskunft_outage_resolved
    id: resolved
  - trigger: event
    event_type: stoerungsauskunft_suspected
    id: suspected
conditions:
  - condition: template
    value_template: "{{ trigger.event.data.get('sector') in ['strom', 'gas', 'wasser'] }}"
actions:
  - variables:
      d: "{{ trigger.event.data }}"
      label: >-
        {{ {'strom': 'Stromausfall', 'gas': 'Gasstörung', 'wasser': 'Wasserstörung',
            'fernwaerme': 'Fernwärmestörung'}.get(d.get('sector'), 'Störung') }}
      maybe: >-
        {{ {'strom': 'Möglicher Stromausfall', 'gas': 'Mögliche Gasstörung', 'wasser': 'Mögliche Wasserstörung',
            'fernwaerme': 'Mögliche Fernwärmestörung'}.get(d.get('sector'), 'Mögliche Störung') }}
      icon: "{{ {'strom': '⚡', 'gas': '🔥', 'wasser': '💧', 'fernwaerme': '♨️'}.get(d.get('sector'), '⚠️') }}"
      place: "{{ [d.get('postal_code'), d.get('city'), d.get('district')] | select | join(' ') }}"
      operator: "{{ d.get('operator') or 'Netzbetreiber unbekannt' }}"
      start_time: >-
        {% set t = as_datetime(d.get('start') or d.get('since'), none) %}{{ as_local(t).strftime('%H:%M') if t else '' }}
      end_time: >-
        {% set t = as_datetime(d.get('end'), none) %}{{ as_local(t).strftime('%H:%M') if t else '' }}
      # gleicher Tag -> "behoben" ersetzt auf dem Handy die Störungsmeldung
      tag: "stoerung-{{ d.get('sector') }}-{{ d.get('postal_code') }}"
  - choose:
      - conditions:
          - condition: trigger
            id: new
        sequence:
          - action: notify.mobile_app_handy
            data:
              title: "{{ icon }} {{ label }} {{ place }}"
              message: >-
                {{ operator }}{% if start_time %}, seit {{ start_time }}{% endif %}
                {%- if end_time %}, Ende vsl. {{ end_time }}{% endif %}
              data:
                tag: "{{ tag }}"
      - conditions:
          - condition: trigger
            id: resolved
        sequence:
          - action: notify.mobile_app_handy
            data:
              title: "✅ {{ label }} behoben {{ place }}"
              message: "{{ operator }}: keine offizielle Störung mehr gemeldet."
              data:
                tag: "{{ tag }}"
      - conditions:
          - condition: trigger
            id: suspected
        sequence:
          - action: notify.mobile_app_handy
            data:
              title: "{{ icon }} {{ maybe }} {{ place }}"
              message: >-
                {{ d.get('reports') }} Bürgermeldungen von {{ d.get('addresses') }} Adressen
                seit {{ start_time }}, {{ 'vom Netzbetreiber bestätigt' if d.get('confirmed')
                else 'noch nicht offiziell bestätigt' }}.
              data:
                tag: "{{ tag }}"
```

Hinweis: Hast du mehrere Einträge mit überlappenden Gebieten (z. B. „Saarland“ und deine eigene PLZ), feuert jedes Ereignis einmal pro Eintrag. Dann in der Bedingung zusätzlich auf einen Eintrag filtern, z. B. `trigger.event.data.config_entry_id == '…'` (die ID steht in der Adresszeile, wenn du den Eintrag unter Einstellungen → Geräte & Dienste → Störungsauskunft öffnest: `…#config_entry=<ID>`).

## Entwicklung

```bash
pip install pytest-homeassistant-custom-component
pytest -q
```

Lizenz: MIT
