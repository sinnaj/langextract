#!/usr/bin/env python3
"""Test the coordinate conversion logic for PDF highlights."""

def test_coordinate_conversion():
    """Test the coordinate conversion from BOTTOMLEFT to TOPLEFT."""
    
    # Test case: Example bbox from our debug data
    bbox = {
        'l': 72.03, 't': 719.91, 'r': 538.43, 'b': 653.09, 
        'coord_origin': 'BOTTOMLEFT'
    }
    
    # Simulate canvas dimensions (typical PDF page)
    canvas_width = 595  # A4 width in points
    canvas_height = 842  # A4 height in points
    scale = 1.0
    
    print("=== COORDINATE CONVERSION TEST ===")
    print(f"Input bbox: {bbox}")
    print(f"Canvas dimensions: {canvas_width}x{canvas_height}")
    print(f"Scale: {scale}")
    
    # Apply the corrected conversion logic
    left = bbox['l'] * scale
    right = bbox['r'] * scale
    
    # In BOTTOMLEFT system: t=719.91 (higher Y), b=653.09 (lower Y)
    # Convert to TOPLEFT: flip relative to canvas height
    pdf_top = bbox['t'] * scale      # 719.91
    pdf_bottom = bbox['b'] * scale   # 653.09
    
    # Convert to canvas TOPLEFT coordinates
    canvas_top = canvas_height - pdf_top        # 842 - 719.91 = 122.09
    canvas_bottom = canvas_height - pdf_bottom  # 842 - 653.09 = 188.91
    
    result = {
        'left': left,
        'top': canvas_top,
        'width': right - left,
        'height': canvas_bottom - canvas_top
    }
    
    print(f"\nConversion results:")
    print(f"  PDF coordinates (BOTTOMLEFT): left={bbox['l']}, top={bbox['t']}, right={bbox['r']}, bottom={bbox['b']}")
    print(f"  Canvas coordinates (TOPLEFT): left={result['left']:.1f}, top={result['top']:.1f}")
    print(f"  Dimensions: width={result['width']:.1f}, height={result['height']:.1f}")
    
    # Validate the conversion
    if result['width'] > 0 and result['height'] > 0:
        print(f"✓ Conversion successful - positive dimensions")
    else:
        print(f"✗ Conversion failed - negative or zero dimensions")
    
    # Test that the coordinate system makes sense
    if result['top'] < result['top'] + result['height']:
        print(f"✓ Coordinate system correct - top < bottom")
    else:
        print(f"✗ Coordinate system incorrect")
    
    return result

if __name__ == "__main__":
    test_coordinate_conversion()