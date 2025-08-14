#!/usr/bin/env python3
"""
Script to integrate Active Jobs functionality into the main app.py
Run this to update your app.py with the new features.
"""

import os
import shutil
from datetime import datetime

def integrate_active_jobs():
    """Integrate Active Jobs tab into main app.py"""
    
    app_file = "src/dashboard/app.py"
    backup_file = f"src/dashboard/app.py.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"📦 Backing up current app.py to {backup_file}")
    shutil.copy(app_file, backup_file)
    
    print("📝 Reading current app.py...")
    with open(app_file, 'r') as f:
        lines = f.readlines()
    
    # Find where to add the import
    import_line_added = False
    for i, line in enumerate(lines):
        if 'from src.dashboard.historical_reprocessing import' in line and not import_line_added:
            # Add Active Jobs import after this line
            lines.insert(i + 1, 'from src.dashboard.active_jobs_tab import display_active_jobs_tab, submit_job_to_queue\n')
            import_line_added = True
            print("✅ Added Active Jobs import")
            break
    
    # Find the tabs definition and update it
    for i, line in enumerate(lines):
        if 'bulk_review_tab, approved_queue_tab, rejected_tab' in line:
            # Found the tab definition line
            # Replace it with the new one including Active Jobs
            lines[i] = 'active_jobs_tab, bulk_review_tab, approved_queue_tab, rejected_tab, analysis_tab, pullthrough_tab, oem_tab, reprocess_tab, export_tab = st.tabs([\n'
            lines[i+1] = '    "🚀 Active Jobs",\n'
            lines[i+2] = '    "Bulk Review",\n'
            # The rest of the tabs should already be there
            print("✅ Updated tab definitions")
            break
    
    # Add Active Jobs tab content after the tabs are defined
    # Find where to insert it (right after the tab definitions)
    for i, line in enumerate(lines):
        if '# ========== BULK REVIEW TAB' in line:
            # Insert Active Jobs tab content before Bulk Review
            active_jobs_content = '''# ========== ACTIVE JOBS TAB ==========
with active_jobs_tab:
    display_active_jobs_tab()

'''
            lines.insert(i, active_jobs_content)
            print("✅ Added Active Jobs tab content")
            break
    
    # Now update the Process Filtered button to use job submission
    # Find the Process Filtered button section
    for i, line in enumerate(lines):
        if 'if st.button("Process Filtered", key=\'process_from_url_filtered\'):' in line:
            print("📝 Updating Process Filtered button to use job queue...")
            
            # Find the end of this button handler (look for the next button or major section)
            end_index = i
            indent_count = 0
            for j in range(i+1, min(i+200, len(lines))):
                if 'if st.button(' in lines[j] and indent_count == 0:
                    end_index = j
                    break
                # Track indentation to find the end of the block
                if lines[j].strip().startswith('if ') and not lines[j].strip().startswith('if '):
                    indent_count += 1
                elif lines[j].strip() == 'else:' and indent_count == 0:
                    end_index = j + 5  # Include the else block
                    break
            
            # Replace the button handler with job submission version
            new_handler = '''        if st.button("Process Filtered", key='process_from_url_filtered'):
            # Only proceed if data has been loaded and filtered
            if 'filtered_df' in locals() and not filtered_df.empty:
                from datetime import datetime
                
                # Convert filtered dataframe to list of records
                records_to_process = filtered_df.to_dict('records')

                # Remap dataframe columns to the format the backend expects
                remapped_records = []
                for record in records_to_process:
                    urls = []
                    if 'Links' in record and pd.notna(record['Links']):
                        urls = [url.strip() for url in str(record['Links']).split(',') if url.strip()]

                    remapped_records.append({
                        'work_order': record.get('WO #'),
                        'model': record.get('Model'),
                        'model_short': record.get('Model Short Name'),
                        'to': record.get('To'),
                        'affiliation': record.get('Affiliation'),
                        'urls': urls,
                        'start_date': record.get('Start Date'),
                        'make': record.get('Make'),
                        'activity_id': record.get('ActivityID'),
                        'person_id': record.get('Person_ID'),
                        'office': record.get('Office')
                    })
                
                # Get user email for job tracking
                user_email = st.session_state.get('user_email', 'anonymous')
                
                # Create job parameters
                job_params = {
                    'url': loans_url,
                    'filters': {
                        'office': selected_office if 'selected_office' in locals() else 'All',
                        'make': selected_make if 'selected_make' in locals() else 'All',
                        'limit': limit_records if 'limit_records' in locals() else 0
                    },
                    'remapped_records': remapped_records
                }
                
                # Create run name
                run_name = f"CSV Process - {len(remapped_records)} records - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                
                try:
                    # Submit job to queue
                    job_id = submit_job_to_queue(
                        job_type='csv_upload',
                        job_params=job_params,
                        run_name=run_name,
                        user_email=user_email
                    )
                    
                    st.success(f"""
                    ✅ **Job submitted successfully!**
                    
                    Job ID: `{job_id[:8]}...`
                    
                    Navigate to the **"🚀 Active Jobs"** tab to monitor progress.
                    """)
                    
                    # Option to switch to Active Jobs tab
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Go to Active Jobs", key="switch_to_active_jobs"):
                            st.session_state.selected_tab = "Active Jobs"
                            st.rerun()
                            
                except Exception as e:
                    st.error(f"❌ Failed to submit job: {str(e)}")
                    logger.error(f"Job submission failed: {e}", exc_info=True)
            else:
                st.warning("No data loaded or no records match filters. Please load data first.")
'''
            
            # Replace the lines
            lines[i:end_index] = [new_handler]
            print("✅ Updated Process Filtered button handler")
            break
    
    # Write the updated file
    print("💾 Writing updated app.py...")
    with open(app_file, 'w') as f:
        f.writelines(lines)
    
    print(f"""
✅ Successfully integrated Active Jobs functionality!

Backup saved to: {backup_file}

To test:
1. Run: ./test_background_jobs_locally.sh
2. Open http://localhost:8501
3. Look for the new '🚀 Active Jobs' tab
4. Submit a job and monitor its progress

To revert if needed:
  cp {backup_file} {app_file}
""")

if __name__ == "__main__":
    integrate_active_jobs()