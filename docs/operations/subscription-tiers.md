# Subscription tier administration

Subscription tiers are stored in MongoDB in the `plans` collection and are controlled from the Admin Control Center.

Administrators can:

- create a tier;
- edit its name, price, currency and duration;
- edit the feature list;
- publish/activate a tier;
- deactivate a tier so new customers cannot select it;
- keep historical subscriptions intact when a tier is deactivated.

Client subscription selection only reads plans where `active=true`. Deactivating a plan does not delete the plan record or rewrite existing subscription history.

Every tier change creates an audit event.
