#!/usr/bin/env python3
"""
Verify Search Accuracy: Check if Google Search is finding the right articles
by analyzing the gap between search targets and actual content found.
"""

import re
import subprocess
from collections import defaultdict

def get_docker_logs():
    """Get Docker logs"""
    try:
        result = subprocess.run(
            ["docker", "logs", subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True).stdout.strip()],
            capture_output=True, text=True
        )
        return result.stdout
    except Exception as e:
        print(f"Error getting Docker logs: {e}")
        return ""

def parse_search_vs_content(logs):
    """
    Parse logs to find what we searched for vs what content we actually got
    """
    
    # Patterns to match
    search_query_pattern = r'Google search attempt \d+/8: (.+)'
    content_pattern = r'Content being sent to GPT \(excerpt\):\s*(.+?)(?=\n2025-\d+-\d+|$)'
    gpt_result_pattern = r'Successfully analyzed content.*?relevance=(\d+)'
    vehicle_search_pattern = r'"([^"]+)" "([^"]+)" review'
    
    analyses = []
    current_analysis = {}
    
    lines = logs.split('\n')
    
    for i, line in enumerate(lines):
        # Capture search queries
        search_match = re.search(search_query_pattern, line)
        if search_match:
            query = search_match.group(1)
            vehicle_match = re.search(vehicle_search_pattern, query)
            if vehicle_match:
                target_vehicle = f"{vehicle_match.group(1)} {vehicle_match.group(2)}"
                current_analysis = {
                    'target_vehicle': target_vehicle,
                    'search_query': query,
                    'content_found': None,
                    'gpt_relevance': None,
                    'is_correct_match': None
                }
        
        # Capture content sent to GPT
        content_match = re.search(r'Content being sent to GPT \(excerpt\):', line)
        if content_match and current_analysis:
            # Get the next line which contains the content
            if i + 1 < len(lines):
                content = lines[i + 1].strip()[:200]  # First 200 chars
                current_analysis['content_found'] = content
        
        # Capture GPT relevance score
        gpt_match = re.search(gpt_result_pattern, line)
        if gpt_match and current_analysis:
            relevance = int(gpt_match.group(1))
            current_analysis['gpt_relevance'] = relevance
            
            # Determine if it's a correct match by checking if target vehicle appears in content
            if current_analysis.get('content_found') and current_analysis.get('target_vehicle'):
                target_words = current_analysis['target_vehicle'].lower().split()
                content_lower = current_analysis['content_found'].lower()
                
                # Check if most target words appear in the content
                matches = sum(1 for word in target_words if word in content_lower)
                current_analysis['is_correct_match'] = matches >= len(target_words) * 0.8  # 80% of words match
                
                analyses.append(current_analysis.copy())
            
            current_analysis = {}
    
    return analyses

def analyze_accuracy(analyses):
    """Analyze the accuracy of search results"""
    
    print("🔍 SEARCH ACCURACY VERIFICATION")
    print("=" * 60)
    
    total_searches = len(analyses)
    correct_matches = sum(1 for a in analyses if a['is_correct_match'])
    wrong_matches = sum(1 for a in analyses if not a['is_correct_match'])
    
    high_relevance_correct = sum(1 for a in analyses if a['is_correct_match'] and a['gpt_relevance'] >= 8)
    high_relevance_wrong = sum(1 for a in analyses if not a['is_correct_match'] and a['gpt_relevance'] >= 8)
    
    print(f"\n📊 OVERALL ACCURACY")
    print(f"Total searches analyzed: {total_searches}")
    print(f"✅ Correct matches: {correct_matches} ({correct_matches/total_searches*100:.1f}%)")
    print(f"❌ Wrong matches: {wrong_matches} ({wrong_matches/total_searches*100:.1f}%)")
    
    print(f"\n🎯 HIGH RELEVANCE ANALYSIS (GPT Score 8+)")
    print(f"✅ High relevance + Correct match: {high_relevance_correct}")
    print(f"❌ High relevance + Wrong match: {high_relevance_wrong}")
    
    if high_relevance_wrong > 0:
        print(f"⚠️  WARNING: {high_relevance_wrong} cases where GPT gave high relevance to wrong articles!")
    
    print(f"\n📋 DETAILED BREAKDOWN")
    print("-" * 60)
    
    for i, analysis in enumerate(analyses[:10]):  # Show first 10
        status = "✅ CORRECT" if analysis['is_correct_match'] else "❌ WRONG"
        print(f"\n{i+1}. {status} (GPT Relevance: {analysis['gpt_relevance']})")
        print(f"   Target: {analysis['target_vehicle']}")
        print(f"   Content: {analysis['content_found'][:100]}...")
        
    # Show examples of potential mismatches
    print(f"\n🚨 EXAMPLES OF POTENTIAL MISMATCHES")
    print("-" * 40)
    
    mismatches = [a for a in analyses if not a['is_correct_match'] and a['gpt_relevance'] >= 5]
    for i, analysis in enumerate(mismatches[:3]):
        print(f"\n{i+1}. Searched for: {analysis['target_vehicle']}")
        print(f"   But found: {analysis['content_found'][:100]}...")
        print(f"   GPT gave it relevance: {analysis['gpt_relevance']}/10")

def main():
    print("Getting Docker logs...")
    logs = get_docker_logs()
    
    if not logs:
        print("❌ No Docker logs found.")
        return
    
    print("Parsing search vs content...")
    analyses = parse_search_vs_content(logs)
    
    if not analyses:
        print("❌ No search patterns found in logs.")
        return
    
    analyze_accuracy(analyses)

if __name__ == "__main__":
    main() 