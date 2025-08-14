"""
Enhanced app.py sections for non-blocking job submission.
This file contains the updated code sections to replace in app.py
"""

# This section replaces the "Process Filtered" button handler (around line 2285-2404)

def handle_process_filtered_with_job_queue():
    """
    Updated handler for Process Filtered button that submits to job queue
    """
    with col2:
        if st.button("Process Filtered", key='process_from_url_filtered'):
            # Only proceed if data has been loaded and filtered
            if 'filtered_df' in locals() and not filtered_df.empty:
                from src.dashboard.active_jobs_tab import submit_job_to_queue
                from datetime import datetime
                
                # Convert filtered dataframe to list of records
                records_to_process = filtered_df.to_dict('records')

                # Remap dataframe columns to the format the backend expects
                remapped_records = []
                for record in records_to_process:
                    # Split the 'Links' string into a list of URLs
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
                    'url': loans_url,  # Store the original URL
                    'filters': {
                        'office': selected_office,
                        'make': selected_make,
                        'reporter': selected_reporter_name,
                        'wo_numbers': wo_number_filter,
                        'activity_ids': activity_id_filter,
                        'start_date': start_date_filter.isoformat() if start_date_filter else None,
                        'end_date': end_date_filter.isoformat() if end_date_filter else None,
                        'skip_records': skip_records
                    },
                    'limit': limit_records,
                    'remapped_records': remapped_records  # Include the pre-filtered records
                }
                
                # Create a descriptive run name
                filter_parts = []
                if selected_office != 'All Offices':
                    filter_parts.append(f"Office:{selected_office}")
                if selected_make != 'All Makes':
                    filter_parts.append(f"Make:{selected_make}")
                if limit_records > 0:
                    filter_parts.append(f"Limit:{limit_records}")
                
                filter_desc = " | ".join(filter_parts) if filter_parts else "All Records"
                run_name = f"CSV Process - {filter_desc} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                
                try:
                    # Submit job to queue
                    job_id = submit_job_to_queue(
                        job_type='csv_upload',
                        job_params=job_params,
                        run_name=run_name,
                        user_email=user_email
                    )
                    
                    # Show success message with link to Active Jobs
                    st.success(f"""
                    ✅ **Job submitted successfully!**
                    
                    Your processing job has been queued and will be processed by the next available worker.
                    
                    **Job ID:** `{job_id[:8]}...`
                    
                    **What's next?**
                    - Navigate to the **"Active Jobs"** tab to monitor progress
                    - You can continue using the dashboard while your job processes
                    - You'll be able to see results in the Bulk Review tab once complete
                    """)
                    
                    # Add a button to navigate to Active Jobs
                    if st.button("📊 Go to Active Jobs", key="go_to_active_jobs"):
                        st.session_state.selected_tab = "Active Jobs"
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"❌ Failed to submit job: {str(e)}")
                    logger.error(f"Job submission failed: {e}", exc_info=True)
            else:
                st.warning("No data loaded or no records match filters. Please load data first.")


# This section adds the Active Jobs tab to the main tab list (around line 2449)
def update_main_tabs():
    """
    Updated tab list to include Active Jobs
    """
    # Create tabs for different user workflows  
    active_jobs_tab, bulk_review_tab, approved_queue_tab, rejected_tab, analysis_tab, pullthrough_tab, oem_tab, reprocess_tab, export_tab = st.tabs([
        "🚀 Active Jobs",  # NEW TAB
        "Bulk Review", 
        "Approved Queue",
        "Rejected/Issues", 
        "Strategic Intelligence",
        "Message Pull-Through",
        "OEM Messaging",
        "Re-Process Historical",
        "Export"
    ])
    
    # Add Active Jobs tab content
    with active_jobs_tab:
        from src.dashboard.active_jobs_tab import display_active_jobs_tab
        display_active_jobs_tab()
    
    # Rest of the tabs remain the same...
    

# This section updates the file upload handler to also use job queue (around line 2422)
def handle_file_upload_with_job_queue():
    """
    Updated handler for file upload that submits to job queue
    """
    if uploaded_file is not None:
        temp_file_path = os.path.join(project_root, "data", "fixtures", "temp_upload.csv")
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        if st.button("Process Uploaded File", use_container_width=True):
            from src.dashboard.active_jobs_tab import submit_job_to_queue
            from datetime import datetime
            
            # Get user email for job tracking
            user_email = st.session_state.get('user_email', 'anonymous')
            
            # Create job parameters for file upload
            job_params = {
                'file_path': temp_file_path,
                'file_name': uploaded_file.name
            }
            
            run_name = f"File Upload - {uploaded_file.name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            try:
                # Submit job to queue
                job_id = submit_job_to_queue(
                    job_type='csv_upload',
                    job_params=job_params,
                    run_name=run_name,
                    user_email=user_email
                )
                
                st.success(f"""
                ✅ **File upload job submitted!**
                
                Job ID: `{job_id[:8]}...`
                
                Navigate to the **"Active Jobs"** tab to monitor progress.
                """)
                
            except Exception as e:
                st.error(f"❌ Failed to submit job: {str(e)}")