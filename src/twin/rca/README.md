# rca

Given a set of open alerts, ranks the assets most likely to be the origin.

1. Alerts are grouped into incidents: a gap of more than 30 minutes between consecutive alerts starts a new one.
2. The asset graph (`graph.py`) holds dependency edges from the topology: `in_rack`, `cooled_by`, `powered_by`, `uplinks_to`, `part_of`.
3. Every alerting device and everything upstream of it is a candidate. A candidate explains the alerts that sit on itself or anywhere downstream.
4. Score = 0.45 coverage (share of incident alerts explained) + 0.25 temporal precedence (share of explained alerts raised after the candidate's own first alert, 0.5 if it has none) + 0.15 precision (share of its monitored footprint that is alerting) + 0.15 own alert severity.
5. The fault kind is guessed from the candidate type: CRAC is `cooling_failure`, PDU is `pdu_overload`, transceiver is `dirty_optics`, a server or switch with a fan alert is `fan_degradation`.

A shared CRAC beats the individual racks it cools, a PDU with its own alert beats the servers behind it, and a lone device with no shared upstream stays on itself.
