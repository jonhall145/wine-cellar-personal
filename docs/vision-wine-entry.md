# Vision-Based Wine Entry

## Overview

Wine Cellar now supports **zero-typing wine entry** using AI-powered vision technology. Simply take a photo of a wine label, and the system automatically extracts wine information and pre-fills the form for you.

This feature uses **Claude AI Vision API** by Anthropic to intelligently analyze wine labels and extract structured data.

---

## How It Works

### Step 1: Scan the Label

1. Navigate to **"Add Wine"** from the main menu
2. Click on **"Scan Label"** (or go directly to `/label-scan/`)
3. Allow camera access when prompted
4. Position the wine label in the frame
5. Tap **"Capture Photo"** when ready
6. Review the captured image
7. Tap **"Use This Photo"** to proceed

**Tips for Best Results:**
- Use good lighting
- Hold the camera steady
- Fill the frame with the label
- Ensure text is in focus
- Avoid glare or reflections

### Step 2: Review Extracted Data

After capturing the photo, you'll be redirected to the wine creation form with:

- **Label Preview**: The captured image displayed at the top
- **Auto-filled Fields**: Form fields populated with extracted data
- **Confidence Indicator**: Badge showing extraction quality
  - ✓ **High Confidence** (green): Most fields accurately extracted
  - ⚠ **Please Verify** (yellow): Some fields may need review
  - ⚡ **Low Confidence** (blue): Manual verification recommended

### Step 3: Verify and Save

1. Review the pre-filled fields
2. Correct any inaccuracies
3. Fill in any missing fields
4. Click **"Save Wine"** to add to your cellar

**Note**: You can always click **"Re-scan Label"** if the extraction wasn't satisfactory.

---

## Extracted Fields

The vision system can automatically extract the following information from wine labels:

### Core Details
- **Wine Name**: Main label text
- **Wine Type**: Red, White, Rosé, Sparkling, Dessert, Fortified, Orange
- **Vintage**: Year of production
- **Country**: Country of origin (as ISO code)
- **Region/Subregion**: Geographic location

### Characteristics
- **Grape Varieties**: List of grapes used (e.g., "Cabernet Sauvignon, Merlot")
- **ABV**: Alcohol by volume percentage
- **Bottle Size**: Volume in ml, converted to size code (Piccolo, Standard, Magnum, etc.)
- **Sweetness**: Dry, Semi-Dry, Sweet, etc.

### Producer Information
- **Vineyard/Producer**: Winery name
- **Barcode**: If visible on label

---

## Configuration

### Requirements

1. **Anthropic API Key**: Required for AI vision processing
2. **HTTPS**: Camera access requires secure connection (or localhost)
3. **Modern Browser**: Supports camera API

### Setup

#### 1. Add API Key

Add your Anthropic API key to your environment:

```bash
# In .env file or environment variables
ANTHROPIC_API_KEY=your_api_key_here
```

#### 2. Install Dependencies

The required packages are already in `requirements/base.txt`:

```bash
pip install -r requirements/base.txt
```

This includes:
- `anthropic==0.40.0` - Claude AI API client
- `pillow==12.0.0` - Image processing

#### 3. HTTPS Configuration

For mobile camera access, you need HTTPS:

```bash
# Development with HTTPS
./run_https.sh
```

See [HTTPS_SETUP.md](../HTTPS_SETUP.md) for details.

---

## Technical Details

### Architecture

```
Label Scanner (React)
    ↓ (captures photo)
Session Storage (base64 image)
    ↓ (on redirect to wine-add)
WineVisionExtractor Service
    ↓ (calls Claude Vision API)
Structured Data Extraction
    ↓ (parses response)
Form Pre-filling
    ↓ (user reviews)
Wine Creation
```

### Vision Extraction Service

**Location**: `wine_cellar/apps/wine/services/vision_extraction.py`

The `WineVisionExtractor` class:
1. Accepts base64-encoded image
2. Sends to Claude Vision API with structured prompt
3. Parses AI response into wine fields
4. Validates and maps to model fields
5. Returns extracted data with confidence scores

### Fallback Mechanism

If the Anthropic API is unavailable:
- Falls back to basic regex extraction
- Extracts vintage, ABV, and volume using patterns
- Returns lower confidence score
- User can still manually enter data

---

## Cost Information

### Claude Vision API Pricing

Using **Claude Haiku 4.5** (optimized for speed and cost):

- **Cost per scan**: ~$0.001-$0.003
- **50 scans/month**: ~$0.05-$0.15
- **Annual cost**: ~$0.60-$1.80

Extremely affordable for personal use!

### Cost Optimization

The system automatically:
- Compresses images before sending
- Uses efficient prompts
- Caches extraction results in session

---

## Troubleshooting

### Camera Access Issues

**Problem**: "Camera access denied"
- **Solution**: Check browser permissions and allow camera access

**Problem**: "HTTPS required"
- **Solution**: Use `./run_https.sh` or access via localhost

**Problem**: "No camera found"
- **Solution**: Ensure device has working camera

### Extraction Issues

**Problem**: No fields extracted / Low confidence
- **Cause**: Poor image quality, complex label, non-English text
- **Solution**: Re-scan with better lighting, or manually enter data

**Problem**: Wrong data extracted
- **Cause**: Label ambiguity, unusual format
- **Solution**: Simply correct the fields manually before saving

**Problem**: API errors in logs
- **Cause**: Missing/invalid API key, network issues
- **Solution**: Check `ANTHROPIC_API_KEY` in environment variables

### API Configuration

**Problem**: "AI vision disabled - API key not configured"
- **Solution**: Add `ANTHROPIC_API_KEY` to your `.env` file

**Problem**: "API call failed: rate limit"
- **Solution**: Wait a moment and try again, or use manual entry

---

## Privacy & Security

### Data Handling

- **Images**: Stored temporarily in session, deleted after wine creation
- **API Calls**: Sent securely to Anthropic's servers
- **No Storage**: Label images are NOT permanently stored in database
- **Session Only**: Extraction results cleared on form submission

### Best Practices

1. Don't scan labels with sensitive personal information
2. Review extracted data before saving
3. Regularly rotate your API keys
4. Monitor API usage for anomalies

---

## Developer Guide

### Customizing Extraction

To modify what fields are extracted, edit the prompt in:

```python
# wine_cellar/apps/wine/services/vision_extraction.py
def _build_extraction_prompt(self) -> str:
    # Modify this prompt to extract additional fields
```

### Field Mapping

To change how extracted values map to model fields:

```python
# wine_cellar/apps/wine/services/vision_extraction.py
def _process_field_value(self, field: str, value: str) -> Any:
    # Add custom processing for new fields
```

### Adding New Fields

1. Update extraction prompt to request new field
2. Add parsing logic in `_parse_claude_response()`
3. Add processing in `_process_field_value()`
4. Update form initial data in `WineCreateView.get_initial()`

---

## Limitations

### Current Limitations

- **API Dependent**: Requires Anthropic API key (free tier available)
- **Image Quality**: Poor photos may result in low accuracy
- **Language**: Best results with English labels
- **Complex Labels**: Artistic/minimal labels may be challenging
- **No OCR Fallback**: Without API key, only basic regex extraction available

### Future Enhancements

Planned improvements:
- [x] Multi-label scanning (front + back) - **Implemented**: Wine detail view now displays thumbnail, front, and back images
- [ ] Batch scanning multiple bottles
- [ ] Offline OCR support (Tesseract)
- [ ] Barcode + vision hybrid approach
- [ ] User correction feedback loop
- [ ] Multi-language prompts

---

## Examples

### High Confidence Extraction

**Input**: Clear photo of Bordeaux wine label

**Extracted**:
- Name: "Château Example"
- Type: Red (RE)
- Vintage: 2018
- Country: FR
- Region: Bordeaux
- Grapes: Cabernet Sauvignon, Merlot
- ABV: 13.5
- Confidence: ✓ High

### Medium Confidence Extraction

**Input**: Photo with some glare

**Extracted**:
- Name: "Example Winery"
- Type: White (WH)
- Vintage: 2020
- (Other fields not found)
- Confidence: ⚠ Please Verify

### Low Confidence / Fallback

**Input**: Blurry or API unavailable

**Extracted**:
- Vintage: 2019 (regex)
- ABV: 12.5 (regex)
- Confidence: ⚡ Low

---

## FAQ

**Q: Do I need to pay for API usage?**
A: Anthropic offers free tier credits. Typical usage is ~$2-3/year for personal wine collections.

**Q: Can I use this offline?**
A: Not currently. The AI vision requires API access. Basic regex extraction works without API.

**Q: What if extraction is wrong?**
A: Simply edit the fields manually before saving. All fields are editable.

**Q: Does it support non-English labels?**
A: Yes, Claude AI supports multiple languages, though accuracy may vary.

**Q: Is my wine data sent to Anthropic?**
A: Only the label image is sent. The extracted data stays in your Wine Cellar instance.

**Q: Can I scan the back label too?**
A: Yes! The wine detail view displays thumbnail, front label, and back label images. You can upload multiple images when adding or editing a wine.

---

## Related Documentation

- [Label Scanner UI](../CLAUDE.md#ui-testing--browser-automation) - Camera component details
- [HTTPS Setup](../HTTPS_SETUP.md) - Camera access configuration
- [Wine Models](models.md) - Database schema for wines
- [API Reference](https://docs.anthropic.com/claude/reference) - Anthropic Claude Vision

---

*Last updated: 2026-01-14*
