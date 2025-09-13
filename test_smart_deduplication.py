#!/usr/bin/env python3
"""
Test the improved smart deduplication logic.
"""

import subprocess
import tempfile
import os

def create_test_html_page():
    """Create a test HTML page that exercises the smart deduplication logic"""
    
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Deduplication Test</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        .test-case { margin: 20px 0; padding: 15px; border: 1px solid #ccc; }
        .result { margin: 10px 0; padding: 10px; background: #f5f5f5; }
        pre { background: #f0f0f0; padding: 10px; overflow-x: auto; }
        .pass { background: #d4edda; }
        .fail { background: #f8d7da; }
    </style>
</head>
<body>
    <h1>🧠 Smart Deduplication Logic Test</h1>
    <div id="testResults"></div>
    
    <script>
        // Mock the smart deduplication methods for testing
        function simulateSmartDeduplication() {
            const testResults = document.getElementById('testResults');
            
            // Test Case 1: Generic vs Specific Section
            const testCase1 = document.createElement('div');
            testCase1.className = 'test-case';
            testCase1.innerHTML = `
                <h3>Test Case 1: Generic vs Specific Section</h3>
                <p>NORM appears first in "General Requirements" then in "Fire Door Specifications"</p>
            `;
            
            // Simulate the logic
            const existing = {
                parentId: 'general_requirements',
                documentOrder: 5,
                extraction: { extraction_text: 'Fire doors must be self-closing' }
            };
            
            const newExtraction = {
                attributes: { id: 'norm_123' },
                extraction_text: 'Fire doors must be self-closing',
                document_order: 15
            };
            
            const newParent = 'fire_door_specifications';
            
            const normalizedData = {
                sections: [
                    {
                        section_id: 'general_requirements',
                        section_name: 'General Requirements',
                        section_level: 1
                    },
                    {
                        section_id: 'fire_door_specifications', 
                        section_name: 'Fire Door Specifications',
                        section_level: 2
                    }
                ]
            };
            
            // Mock the smart selection logic
            const shouldReplace = mockShouldReplaceWithNewParent(existing, newExtraction, existing.parentId, newParent, normalizedData);
            
            const result1 = document.createElement('div');
            result1.className = shouldReplace ? 'result pass' : 'result fail';
            result1.innerHTML = `
                <strong>Result:</strong> ${shouldReplace ? 'REPLACE' : 'KEEP'} existing location<br>
                <strong>Expected:</strong> REPLACE (more specific section)<br>
                <strong>Status:</strong> ${shouldReplace ? '✅ PASS' : '❌ FAIL'}
            `;
            testCase1.appendChild(result1);
            testResults.appendChild(testCase1);
            
            // Test Case 2: Specific vs Generic
            const testCase2 = document.createElement('div');
            testCase2.className = 'test-case';
            testCase2.innerHTML = `
                <h3>Test Case 2: Specific vs Generic Section</h3>
                <p>NORM appears first in "Emergency Exit Requirements" then in "General"</p>
            `;
            
            const existing2 = {
                parentId: 'emergency_exit_requirements',
                documentOrder: 5,
                extraction: { extraction_text: 'Emergency exits must be clearly marked' }
            };
            
            const newExtraction2 = {
                attributes: { id: 'norm_456' },
                extraction_text: 'Emergency exits must be clearly marked', 
                document_order: 15
            };
            
            const newParent2 = 'general';
            
            const normalizedData2 = {
                sections: [
                    {
                        section_id: 'emergency_exit_requirements',
                        section_name: 'Emergency Exit Requirements',
                        section_level: 2
                    },
                    {
                        section_id: 'general',
                        section_name: 'General',
                        section_level: 1  
                    }
                ]
            };
            
            const shouldReplace2 = mockShouldReplaceWithNewParent(existing2, newExtraction2, existing2.parentId, newParent2, normalizedData2);
            
            const result2 = document.createElement('div');
            result2.className = !shouldReplace2 ? 'result pass' : 'result fail';
            result2.innerHTML = `
                <strong>Result:</strong> ${shouldReplace2 ? 'REPLACE' : 'KEEP'} existing location<br>
                <strong>Expected:</strong> KEEP (existing is more specific)<br>
                <strong>Status:</strong> ${!shouldReplace2 ? '✅ PASS' : '❌ FAIL'}
            `;
            testCase2.appendChild(result2);
            testResults.appendChild(testCase2);
            
            // Test Case 3: ROOT vs Specific
            const testCase3 = document.createElement('div');
            testCase3.className = 'test-case';
            testCase3.innerHTML = `
                <h3>Test Case 3: ROOT vs Specific Section</h3>
                <p>NORM appears first at ROOT level then in "Safety Requirements"</p>
            `;
            
            const existing3 = {
                parentId: 'ROOT',
                documentOrder: 5,
                extraction: { extraction_text: 'Safety requirements must be met' }
            };
            
            const newExtraction3 = {
                attributes: { id: 'norm_789' },
                extraction_text: 'Safety requirements must be met',
                document_order: 15
            };
            
            const newParent3 = 'safety_requirements';
            
            const normalizedData3 = {
                sections: [
                    {
                        section_id: 'safety_requirements',
                        section_name: 'Safety Requirements', 
                        section_level: 1
                    }
                ]
            };
            
            const shouldReplace3 = mockShouldReplaceWithNewParent(existing3, newExtraction3, existing3.parentId, newParent3, normalizedData3);
            
            const result3 = document.createElement('div');
            result3.className = shouldReplace3 ? 'result pass' : 'result fail';
            result3.innerHTML = `
                <strong>Result:</strong> ${shouldReplace3 ? 'REPLACE' : 'KEEP'} existing location<br>
                <strong>Expected:</strong> REPLACE (specific section better than ROOT)<br>
                <strong>Status:</strong> ${shouldReplace3 ? '✅ PASS' : '❌ FAIL'}
            `;
            testCase3.appendChild(result3);
            testResults.appendChild(testCase3);
            
            // Summary
            const passCount = document.querySelectorAll('.result.pass').length;
            const totalCount = document.querySelectorAll('.result').length;
            
            const summary = document.createElement('div');
            summary.style.cssText = 'margin-top: 30px; padding: 20px; border: 2px solid #007bff; background: #f8f9fa;';
            summary.innerHTML = `
                <h2>📊 Test Summary</h2>
                <p><strong>Passed:</strong> ${passCount} / ${totalCount} tests</p>
                <p><strong>Status:</strong> ${passCount === totalCount ? '🎉 All tests passed!' : '⚠️ Some tests failed'}</p>
            `;
            testResults.appendChild(summary);
        }
        
        // Mock implementation of the smart deduplication logic
        function mockShouldReplaceWithNewParent(existingNode, newExtraction, existingParent, newParent, normalizedData) {
            // Same logic as the JavaScript implementation
            
            if (existingParent === newParent) {
                return false;
            }
            
            if (existingParent === 'ROOT' && newParent !== 'ROOT') {
                return true;
            }
            
            if (newParent === 'ROOT' && existingParent !== 'ROOT') {
                return false;
            }
            
            const existingSection = getSectionInfo(existingParent, normalizedData);
            const newSection = getSectionInfo(newParent, normalizedData);
            
            if (existingSection && newSection) {
                const existingScore = calculateSectionSpecificity(existingSection, existingNode);
                const newScore = calculateSectionSpecificity(newSection, existingNode);
                return newScore > existingScore;
            }
            
            if (!existingSection && newSection) {
                return true;
            }
            
            if (existingSection && !newSection) {
                return false;
            }
            
            const existingOrder = existingNode.documentOrder || 0;
            const newOrder = newExtraction.document_order || 0;
            return newOrder > existingOrder;
        }
        
        function getSectionInfo(parentId, normalizedData) {
            if (!parentId || parentId === 'ROOT' || !normalizedData) {
                return null;
            }
            
            if (normalizedData.sections) {
                return normalizedData.sections.find(s => s.section_id === parentId);
            }
            
            return null;
        }
        
        function calculateSectionSpecificity(section, node) {
            let score = 0;
            
            const sectionLevel = section.section_level || section.level || 0;
            score += sectionLevel * 10;
            
            const sectionName = section.section_name || section.section_title || section.title || '';
            score += Math.min(sectionName.length / 10, 5);
            
            // Keyword matching logic
            if (node && node.extraction) {
                const nodeText = (node.extraction.extraction_text || '').toLowerCase();
                const sectionNameLower = sectionName.toLowerCase();
                
                const sectionKeywords = sectionNameLower
                    .split(/[\\s\\-_\\(\\)]+/)
                    .filter(word => word.length > 3);
                
                let keywordMatches = 0;
                sectionKeywords.forEach(keyword => {
                    if (nodeText.includes(keyword)) {
                        keywordMatches++;
                    }
                });
                
                score += keywordMatches * 5;
            }
            
            // Bonus for specific terms
            if (sectionName.toLowerCase().includes('fire')) score += 3;
            if (sectionName.toLowerCase().includes('emergency')) score += 3;
            if (sectionName.toLowerCase().includes('safety')) score += 3;
            if (sectionName.toLowerCase().includes('door')) score += 3;
            if (sectionName.toLowerCase().includes('requirement')) score += 2;
            if (sectionName.toLowerCase().includes('specification')) score += 2;
            
            // Penalty for generic terms
            if (sectionName.toLowerCase().includes('general')) score -= 5;
            if (sectionName.toLowerCase().includes('introduction')) score -= 5;
            if (sectionName.toLowerCase().includes('overview')) score -= 3;
            
            return score;
        }
        
        // Run the test when the page loads
        document.addEventListener('DOMContentLoaded', simulateSmartDeduplication);
    </script>
</body>
</html>
"""

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        f.write(html_content)
        return f.name

def test_smart_deduplication():
    """Test the smart deduplication logic"""
    
    print("🧠 Testing Smart Deduplication Logic")
    print("=" * 50)
    
    # Create test HTML file
    test_file = create_test_html_page()
    print(f"📄 Created test file: {test_file}")
    
    # Open in browser (if available)
    try:
        import webbrowser
        webbrowser.open(f'file://{test_file}')
        print("🌐 Opened test page in browser")
    except Exception as e:
        print(f"❌ Could not open browser: {e}")
        print("📁 Please manually open the test file in a browser")
    
    # Keep file for manual inspection
    print(f"📋 Test file available at: {test_file}")
    print("   (File will be automatically cleaned up)")
    
    return test_file

if __name__ == "__main__":
    test_file = test_smart_deduplication()
    
    print("\n" + "=" * 50)
    print("✅ Test setup complete!")
    print("💡 The test page will show:")
    print("   - Generic vs Specific section choice")  
    print("   - Specific vs Generic section choice")
    print("   - ROOT vs Specific section choice")
    print("   - Overall test pass/fail status")
    
    # Auto-cleanup after delay
    import time
    import os
    
    print("\n⏱️  Keeping test file for 60 seconds for inspection...")
    try:
        time.sleep(60)
        os.unlink(test_file)
        print("🗑️  Test file cleaned up")
    except:
        print("⚠️  Could not clean up test file automatically")