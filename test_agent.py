from foundry import analyze_transcript


sample_transcript = """
Rahul: We need to launch the new dashboard.
Priya: Friday is too early. Monday would be safer because testing is still pending.
Rahul: Okay, let's move the launch to Monday.
Aman: I'll prepare the deployment checklist.
Priya: I'll review the dashboard today.
Rahul: Can someone check the customer feedback?
Aman: I can do that, but I may need support-team help.
Priya: We still haven't decided who will handle the final approval.
"""

result = analyze_transcript(sample_transcript)

print("\n===== MEETASSIST AGENT RESULT =====\n")
print(result)