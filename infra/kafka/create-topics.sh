#!/bin/bash
# Create all 6 Kafka topics with 7-day retention
# Run: make kafka-setup
# Or: docker exec riskcore-kafka-1 bash /path/to/this/script

BOOTSTRAP_SERVER=${1:-localhost:9092}
TOPICS=(
  "policy.created"
  "policy.updated"
  "policy.cancelled"
  "claim.filed"
  "claim.status_changed"
  "claim.resolved"
)

for topic in "${TOPICS[@]}"; do
  echo "Creating topic: $topic"
  kafka-topics --create \
    --topic "$topic" \
    --partitions 3 \
    --replication-factor 1 \
    --config retention.ms=604800000 \
    --bootstrap-server "$BOOTSTRAP_SERVER" \
    --if-not-exists
done

echo ""
echo "Topics:"
kafka-topics --list --bootstrap-server "$BOOTSTRAP_SERVER"
