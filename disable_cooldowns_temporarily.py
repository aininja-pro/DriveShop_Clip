#!/usr/bin/env python3
"""
Temporary patch to disable cooldowns for testing
This modifies the code to bypass cooldown checks - USE WITH CAUTION!
"""

import os
import shutil
from datetime import datetime

def create_backup(file_path):
    """Create a backup of the file before modifying"""
    backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(file_path, backup_path)
    print(f"✅ Backup created: {backup_path}")
    return backup_path

def disable_cooldowns():
    """Patch files to disable cooldown checks"""
    
    modifications = []
    
    # 1. Patch database.py to always return True for should_retry_wo
    db_file = "src/utils/database.py"
    print(f"\n📝 Modifying {db_file}...")
    
    backup = create_backup(db_file)
    modifications.append((db_file, backup))
    
    with open(db_file, 'r') as f:
        content = f.read()
    
    # Find and modify should_retry_wo method
    original = """    def should_retry_wo(self, wo_number: str) -> bool:
        \"\"\"
        Check if a WO# should be retried based on smart retry logic"""
    
    patched = """    def should_retry_wo(self, wo_number: str) -> bool:
        \"\"\"
        Check if a WO# should be retried based on smart retry logic
        
        TEMPORARY: COOLDOWNS DISABLED FOR TESTING"""
    
    if original in content:
        # Add early return to bypass cooldown check
        patched_content = content.replace(original, patched)
        patched_content = patched_content.replace(
            '        Returns:\n            bool: True if should retry, False otherwise\n        """\n        try:',
            '        Returns:\n            bool: True if should retry, False otherwise\n        """\n        # TEMPORARY: Return True to bypass cooldowns during testing\n        return True\n        \n        try:'
        )
        
        with open(db_file, 'w') as f:
            f.write(patched_content)
        print(f"✅ Patched {db_file} - should_retry_wo will always return True")
    else:
        print(f"⚠️  Could not find method to patch in {db_file}")
    
    # 2. Patch ingest_database.py to skip cooldown check
    ingest_file = "src/ingest/ingest_database.py"
    print(f"\n📝 Modifying {ingest_file}...")
    
    backup = create_backup(ingest_file)
    modifications.append((ingest_file, backup))
    
    with open(ingest_file, 'r') as f:
        content = f.read()
    
    # Change retry_cooldown to skip_already_found (so it doesn't skip)
    original_check = """                elif clip_status in ['no_content_found', 'processing_failed']:
                    skip_reason = 'retry_cooldown'"""
    
    patched_check = """                elif clip_status in ['no_content_found', 'processing_failed']:
                    # TEMPORARY: Disabled cooldown for testing
                    skip_reason = 'testing_no_cooldown'
                    # skip_reason = 'retry_cooldown'  # Original line"""
    
    if original_check in content:
        patched_content = content.replace(original_check, patched_check)
        
        # Also modify the skip logic to not skip during testing
        patched_content = patched_content.replace(
            "            # Record the skip event\n            db.record_skip_event(wo_number, run_id, skip_reason)\n            logger.info(f\"⏭️ Skipping {wo_number} - {skip_reason}\")\n            return False",
            "            # TEMPORARY: Don't skip during testing if it's a cooldown\n            if skip_reason != 'testing_no_cooldown':\n                # Record the skip event\n                db.record_skip_event(wo_number, run_id, skip_reason)\n                logger.info(f\"⏭️ Skipping {wo_number} - {skip_reason}\")\n                return False\n            else:\n                logger.info(f\"🔄 TESTING MODE: Processing {wo_number} despite cooldown\")"
        )
        
        with open(ingest_file, 'w') as f:
            f.write(patched_content)
        print(f"✅ Patched {ingest_file} - cooldown skips disabled")
    else:
        print(f"⚠️  Could not find cooldown check to patch in {ingest_file}")
    
    print("\n" + "=" * 60)
    print("✅ COOLDOWNS TEMPORARILY DISABLED FOR TESTING")
    print("=" * 60)
    print("\n⚠️  IMPORTANT: Restore original files when done testing!")
    print("\nBackups created:")
    for original, backup in modifications:
        print(f"  - {backup}")
    
    # Save restoration script
    restore_script = "restore_cooldowns.sh"
    with open(restore_script, 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("# Restore original files from backups\n\n")
        for original, backup in modifications:
            f.write(f"echo 'Restoring {original}...'\n")
            f.write(f"cp '{backup}' '{original}'\n")
        f.write("\necho '✅ Original files restored!'\n")
    
    os.chmod(restore_script, 0o755)
    print(f"\nRestore script created: ./{restore_script}")
    print("Run this script to restore original cooldown behavior")

def restore_cooldowns():
    """Restore original files from most recent backups"""
    import glob
    
    files_to_restore = [
        "src/utils/database.py",
        "src/ingest/ingest_database.py"
    ]
    
    for file_path in files_to_restore:
        # Find most recent backup
        backups = glob.glob(f"{file_path}.backup_*")
        if backups:
            backups.sort()
            latest_backup = backups[-1]
            print(f"Restoring {file_path} from {latest_backup}")
            shutil.copy2(latest_backup, file_path)
            print(f"✅ Restored {file_path}")
        else:
            print(f"⚠️  No backup found for {file_path}")
    
    print("\n✅ Cooldown checks restored to normal behavior")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        print("🔄 Restoring original cooldown behavior...")
        restore_cooldowns()
    else:
        print("🚀 Disabling cooldowns for testing...")
        print("⚠️  This will modify source files - make sure to restore them later!")
        
        confirm = input("\nProceed? (yes/no): ").strip().lower()
        if confirm == 'yes':
            disable_cooldowns()
        else:
            print("Cancelled")
            print("\nTo restore original files later, run:")
            print("  python disable_cooldowns_temporarily.py restore")