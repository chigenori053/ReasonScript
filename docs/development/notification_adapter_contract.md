# Notification Adapter Contract

Specification: `reasonscript-ide/command-settings-notification-adapter/phase-4-c`

Notifications are platform-bound user messages with three levels:

```txt
info
warning
error
```

Each notification accepts a message and optional metadata:

```txt
title
operation
details
durationMs
```

Browser Phase 4-C uses console fallback notifications. Desktop native
notifications are deferred to the desktop shell phase.

Command failures and adapter failures should pass through the notification
adapter through the `PlatformError` mapping helper.
