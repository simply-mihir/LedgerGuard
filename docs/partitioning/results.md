# Journal partitioning study

PostgreSQL 17.11. Every probe runs in a throwaway schema; no ledger table is touched.

| Probe | Supports 'partitioning weakens the ledger' | Summary |
|---|---|---|
| `unique_needs_partition_key` | yes | PostgreSQL refuses PRIMARY KEY(journal_id), UNIQUE(sequence_number) and an FK to journal_id on a table partitioned by created_at. |
| `compliant_shape_loses_global_uniqueness` | yes | With the partition key in the unique constraints, a duplicate journal_id or sequence_number in another partition is accepted; the unpartitioned table rejects both. |
| `lines_lookup_fans_out` | yes | Lookups by journal_id (the balanced-journal trigger and the hash-chain sealer) probe all 8 partitions; only account-keyed lookups prune to one. |
| `partition_drop_bypasses_immutability` | yes | DELETE and TRUNCATE are blocked by the immutability triggers, but DETACH PARTITION and DROP of a partition remove history without firing either. |

## Raw observations

```json
{
  "compliant_shape_loses_global_uniqueness": {
    "results": {
      "part.duplicate_journal_id": "ACCEPTED",
      "part.duplicate_sequence_number": "ACCEPTED",
      "plain.duplicate_journal_id": "REJECTED 23505",
      "plain.duplicate_sequence_number": "REJECTED 23505"
    }
  },
  "lines_lookup_fans_out": {
    "partitions": 8,
    "relations_touched": {
      "by_account_id": {
        "partitioned": 1,
        "unpartitioned": 1
      },
      "by_journal_id": {
        "partitioned": 8,
        "unpartitioned": 1
      }
    }
  },
  "partition_drop_bypasses_immutability": {
    "outcome": {
      "delete_row": "BLOCKED 55000",
      "detach_partition": "ALLOWED",
      "drop_partition": "ALLOWED",
      "rows_left_after": "1",
      "truncate": "BLOCKED 55000"
    }
  },
  "unique_needs_partition_key": {
    "attempts": {
      "lines_fk_to_journal_id": "REFUSED 42830",
      "primary_key_journal_id": "REFUSED 0A000",
      "unique_sequence_number": "REFUSED 0A000"
    }
  }
}
```
