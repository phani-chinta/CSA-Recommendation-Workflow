# Data dictionary

All records are synthetic. Timestamps are UTC. Required fields are marked **required**; optional fields permit blank/null. Primary IDs are immutable strings. Validation is enforced by field types, choices, unique constraints or generator/service checks as indicated.

| Entity | Field | Type / unit | Required | Allowed / uniqueness / validation |
|---|---|---|---|---|
| Customer | id | string | yes | PK, `CUS-` + six digits |
| Customer | first_name, last_name | string | yes | 1–40 chars |
| Customer | email | email | yes | unique; synthetic `.test` domain |
| Customer | region | string | yes | North/South/East/West/Central in generator |
| Customer | joined_at | date | yes | not after as-of date |
| Customer | lifecycle | enum | yes | new/active/dormant |
| Customer | created_at | timestamp | system | creation time |
| Product | id | string | yes | PK, `PRD-` |
| Product | name, category | string | yes | product label and taxonomy category |
| Product | unit_price | decimal USD | yes | nonnegative currency amount |
| Product | active | boolean | yes | catalog eligibility |
| Order | id | string | yes | PK, `ORD-YYYY-` + six digits |
| Order | customer | FK Customer | yes | existing customer; delete protected |
| Order | ordered_at | timestamp | yes | at or before processing as-of time |
| Order | status | enum | yes | completed/returned/cancelled |
| Order | total | decimal USD | yes | sum of order lines; exception can be labeled |
| Order | issue_type | string | no | blank or documented anomaly label |
| OrderLine | id | string | yes | PK, order ID + line suffix |
| OrderLine | order, product | FKs | yes | existing parent records |
| OrderLine | quantity | positive integer | yes | >0 |
| OrderLine | unit_price, line_total | decimal USD | yes | line_total = quantity × unit_price; reconcile to order |
| OrderLine | product_snapshot | JSON object | yes | frozen product ID, name, category and price at purchase time |
| EngagementEvent | id | string | yes | PK, `EVT-` + nine digits |
| EngagementEvent | customer | FK Customer | yes | existing customer |
| EngagementEvent | event_type | string | yes | email_open/email_click/web_visit/app_session/purchase_view |
| EngagementEvent | occurred_at | timestamp | yes | valid event timestamp |
| EngagementEvent | channel | string | yes | email/sms/push |
| EngagementEvent | campaign | string | no | synthetic campaign reference |
| SupportCase | id | string | yes | PK, `CASE-` |
| SupportCase | customer | FK Customer | yes | existing customer |
| SupportCase | opened_at, resolved_at | timestamps | opened required; resolved optional | resolved_at >= opened_at |
| SupportCase | category | string | yes | billing/delivery/product/other |
| SupportCase | status | enum | yes | open/resolved; resolved date consistent with state |
| SupportCase | service_cost | decimal USD | yes | >=0; >=100 is high service cost |
| SupportCase | description | text | no | operator-entered case context |
| Consent | id | string | yes | PK, `CNS-` |
| Consent | customer | FK Customer | yes | existing customer |
| Consent | channel | enum | yes | email/sms/push; one current decision per customer/channel expected |
| Consent | is_allowed | boolean | yes | false means suppress contact |
| Consent | effective_from, effective_to | timestamps | from required; to optional | effective_to > effective_from; records retained as history; latest effective decision governs channel eligibility |
| Consent | source | string | yes | synthetic_preference in generator |
| SegmentRule | id | string | yes | PK, `SEG-YYYY-` + six digits |
| SegmentRule | name, description | string/text | yes | unique business name recommended; rationale documented |
| SegmentRule | priority | positive integer | yes | lower value wins exclusive tie-break |
| SegmentRule | exclusive, active | booleans | yes | controls membership and eligibility |
| SegmentRule | effective_from, effective_to | dates | from required; to optional | end date after start |
| SegmentMembership | id | string | yes | PK, `MEM-<segment>-<customer>-<timestamp>` |
| SegmentMembership | segment, customer | FKs | yes | existing rule and customer |
| SegmentMembership | assigned_at | timestamp | yes | immutable decision time |
| SegmentMembership | reason | text | yes | human-readable decision evidence |
| SegmentMembership | score | decimal | yes | calculated from source purchase/service data |
| SegmentMembership | is_current | boolean | yes | one current exclusive membership per customer; prior rows retained |
| SegmentMembership | issue_type | string | no | explicit exception label, blank normally |
| SegmentMembership | rule_snapshot | JSON object | yes | frozen rule ID/name/description/priority/effective dates used for this decision |
| ActionCatalog | id | string | yes | PK, `CAT-` in implementation |
| ActionCatalog | name, description | string/text | yes | operator-readable action |
| ActionCatalog | channel | enum | yes | email/sms/push; must match consent channel |
| ActionCatalog | segment | FK SegmentRule | yes | eligible segment; segment 1:N actions |
| ActionCatalog | priority | positive integer | yes | ascending execution order |
| ActionCatalog | active | boolean | yes | inactive action ignored |
| ActionCatalog | cooldown_days | positive integer | yes | minimum gap before next recommendation |
| ActionCatalog | effective_from, effective_to | dates | from required; to optional | end must follow start; only effective actions are eligible |
| ActionOutcome | id | string | yes | PK, `ACTN-YYYY-` + zero-padded sequence |
| ActionOutcome | action, customer | FKs | yes | exact catalog action and target customer |
| ActionOutcome | recommended_at | timestamp | yes | decision time |
| ActionOutcome | status | enum | yes | recommended/suppressed/sent/converted/not_converted |
| ActionOutcome | suppression_reason | string | no | consent_missing_or_withdrawn or cooldown |
| ActionOutcome | outcome_at | timestamp | no | required for completed conversion/non-conversion |
| ActionOutcome | revenue | decimal USD | yes | nonnegative attributed revenue; conversion only contributes to metric |
| ActionOutcome | issue_type | string | no | labeled known anomaly, blank in normal records |
| ActionOutcome | action_snapshot | JSON object | yes | frozen action catalog definition when recommended |
| ActionOutcomeEvent | id | integer | system | primary key |
| ActionOutcomeEvent | outcome | FK ActionOutcome | yes | protected history owner |
| ActionOutcomeEvent | from_status, to_status | strings | from optional for creation; to required | each state change is appended |
| ActionOutcomeEvent | changed_at, changed_by | timestamp / FK user | time required; user optional | UTC time and operator reference |
| ActionOutcomeEvent | actor_label, notes | string / text | optional | readable actor snapshot and operator context |
| ActionOutcomeEvent | revenue, provider_reference | decimal / string | optional | conversion amount and delivery correlation |
| SupportCaseEvent | id | integer | system | primary key |
| SupportCaseEvent | case | FK SupportCase | yes | protected history owner |
| SupportCaseEvent | from_status, to_status | strings | from optional; to required | reopen requires an explanation |
| SupportCaseEvent | changed_at, changed_by, actor_label, notes | timestamp/FK/string/text | time required; others optional | append-only support case history |
| WorkflowRun | id | UUID | system | primary key |
| WorkflowRun | operation, status | enums | yes | segment/recommend; queued/running/succeeded/failed |
| WorkflowRun | requested_by | FK user | optional | operator who enqueued the job |
| WorkflowRun | requested_at, started_at, finished_at | timestamps | requested required; others optional | job lifecycle timestamps |
| WorkflowRun | attempts | positive integer | yes | worker attempts before stale-run recovery gives up |
| WorkflowRun | result | JSON object | yes | aggregate workflow output |
| WorkflowRun | error | text | optional | sanitized operator message; details remain in worker logs |

## Cardinality and optionality

Customer has many order, event, support, consent, membership and action records. An order has one customer and many lines. A line has one product. Product/order is many-to-many through OrderLine. SegmentRule has many memberships and actions. Each membership references exactly one customer and one rule. Each action outcome references exactly one catalog action and customer. Consent end time and support resolution time are optional. Segment effective end and action outcome time are optional until closed.
