# VPN Troubleshooting Guide

This document provides solutions for common VPN connectivity issues.

## Issue 1: VPN Connection Drops Intermittently

**Symptoms:**
- VPN connects successfully but disconnects after a few minutes
- Connection drops during video calls or large file transfers
- Error message: "Connection timed out" or "Server not responding"

**Troubleshooting Steps:**

1. **Check your internet stability**
   - Run a speed test at speedtest.net
   - Ensure you have at least 10 Mbps download/upload speed
   - Try connecting via ethernet cable instead of WiFi

2. **Adjust VPN client settings**
   - Open the VPN client settings
   - Disable "Auto-disconnect on idle"
   - Change protocol from UDP to TCP (more stable, slightly slower)
   - Reduce MTU size to 1400 in advanced settings

3. **Update VPN client**
   - Check for updates in the VPN client (Help > Check for Updates)
   - Minimum supported version: 4.2.1
   - Restart your computer after updating

4. **Disable conflicting software**
   - Temporarily disable third-party firewalls
   - Check if other VPN clients are installed and disable them
   - Disable battery saver mode on laptops

If the issue persists after these steps, contact IT Support via the help desk portal.

## Issue 2: VPN Authentication Failure

**Symptoms:**
- Error message: "Authentication failed" or "Invalid credentials"
- Login screen keeps reappearing after entering credentials
- Error code: AUTH_001 or AUTH_003

**Troubleshooting Steps:**

1. **Verify your credentials**
   - Ensure you're using your network username (not email)
   - Check that CAPS LOCK is not enabled
   - Try resetting your password via the self-service portal at https://password.company.com

2. **Check certificate validity**
   - Open the VPN client and go to Settings > Certificates
   - Verify the certificate hasn't expired
   - If expired, click "Renew Certificate" and follow the prompts

3. **Clear cached credentials**
   - Windows: Control Panel > Credential Manager > Remove VPN entries
   - Mac: Keychain Access > Search "VPN" > Delete related entries
   - Restart the VPN client

4. **Escalate to IT Security**

   If none of the above steps resolve the authentication issue, this may indicate an account lockout or security flag on your profile.

   **Create a Jira ticket** in the IT-SECURITY project:
   - Issue type: Support Request
   - Summary: "VPN Authentication Failure - [Your Name]"
   - Description: Include the error code, your username, and steps you've already tried
   - Priority: High (if blocking your work)
   - Component: VPN/Remote Access

   The IT Security team will review your account status and respond within 4 business hours.

---

*Last updated: January 2026*
*Emergency IT Support: ext. 5555 or it-emergency@company.com*
