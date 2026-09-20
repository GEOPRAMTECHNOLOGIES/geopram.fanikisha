def automation_matches(trigger, text): return bool(trigger and text and trigger.lower() in text.lower())
