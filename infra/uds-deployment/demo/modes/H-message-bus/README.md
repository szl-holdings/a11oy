# Mode H — Kafka/NATS message bus (DOCUMENTATION ONLY)
No live switch. Today receipts fan out via HTTP POST to szl-receipts-server
`/v1/append`. A broker sink is a ~1-day refactor of szl-receipts-server
(PR-stage at szl-uds-deployment#19). `run.sh` prints the design + exits 7.
