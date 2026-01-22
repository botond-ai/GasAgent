# Office Printer Guide

This document provides information about printer locations, capabilities, and basic troubleshooting.

## Printer Locations and Capabilities

### Floor 1 - Reception & Sales

| Printer Name | Location | Type | Features |
|--------------|----------|------|----------|
| PRN-F1-RECEPTION | Reception desk area | HP LaserJet Pro | B&W only, single-sided |
| PRN-F1-SALES | Sales bullpen, near window | Canon imageRUNNER | Color, duplex, scan, fax |

**Best for:** Quick prints, client-facing documents, sales materials

### Floor 2 - Engineering & Product

| Printer Name | Location | Type | Features |
|--------------|----------|------|----------|
| PRN-F2-ENG-EAST | East wing, by the coffee station | Xerox VersaLink | Color, duplex, A3 support |
| PRN-F2-ENG-WEST | West wing, near meeting room 2B | HP LaserJet Enterprise | B&W, high-speed (60 ppm), stapling |
| PRN-F2-PRODUCT | Product team area, center | Epson EcoTank | Color, photo quality, wide format |

**Best for:** Technical documentation, architecture diagrams, large format prints

### Floor 3 - Finance, HR & Executive

| Printer Name | Location | Type | Features |
|--------------|----------|------|----------|
| PRN-F3-FINANCE | Finance department, secure room | Lexmark MS826 | B&W, secure print (badge required) |
| PRN-F3-HR | HR office corridor | Canon PIXMA | Color, duplex, confidential printing |
| PRN-F3-EXEC | Executive suite | HP OfficeJet Pro | Color, wireless, scan to email |

**Best for:** Confidential documents, financial reports, HR materials

## How to Add a Printer

1. Open **Settings > Printers & Scanners** on your computer
2. Click "Add a printer"
3. Select the printer by name from the network list (all start with `PRN-`)
4. Drivers will install automatically
5. Set your preferred default printer

For secure printers (PRN-F3-FINANCE), contact IT to enable badge access on your employee card.

## Troubleshooting: Print Job Stuck in Queue

**Symptoms:**
- Document shows as "Printing" but nothing comes out
- Multiple jobs accumulating in the print queue
- Printer appears online but unresponsive

**Resolution Steps:**

1. **Check the physical printer**
   - Verify the printer is powered on and not showing error lights
   - Check for paper jams (open all trays and access panels)
   - Ensure paper trays are loaded and not empty

2. **Clear your local print queue**
   - Windows: Open Services > Stop "Print Spooler" > Delete files in `C:\Windows\System32\spool\PRINTERS` > Start "Print Spooler"
   - Mac: System Preferences > Printers & Scanners > Select printer > Open Queue > Cancel all jobs

3. **Restart the print job**
   - Remove the printer from your computer
   - Re-add it following the steps above
   - Try printing a test page first

4. **Check network connectivity**
   - Ensure you're connected to the office network (not guest WiFi)
   - VPN users: Disconnect and reconnect to VPN, then retry

If the printer itself appears jammed or shows a hardware error code on its display, do not attempt to fix it yourself. Place an "Out of Order" note on the printer and report it to Facilities at facilities@company.com or ext. 4200.

---

*Printer supplies (toner, paper) are restocked weekly. For urgent supply requests, contact Office Management.*
*Last updated: January 2026*
