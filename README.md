# FIDES - Federated Intelligence for Document & Entity Screening

A multi-stage pipeline for risk assessment in international trade and shipping using AI-powered document analysis, entity extraction, and federated risk fingerprinting.

## Overview

FIDES is a full-stack web application designed to help compliance officers and trade analysts detect suspicious patterns, sanction violations, and document tampering in shipment documentation. The system combines advanced techniques across multiple stages of analysis:

- **Multi-Modal Document Ingestion** (PDF, PNG, JPG) with OCR support
- **AI-Powered Entity Extraction** using large language models (Gemini)
- **5-Layer Enrichment Checks** (sanctions, AIS tracking, pricing, addresses, corporate identity)
- **Federated Risk Fingerprinting** with cross-broker intelligence network
- **Automated Tamper Detection** (image anomalies and document inconsistencies)
- **Explainable Risk Reports** (human-readable summaries with detailed findings)
- **Interactive Question-Answering Chatbot** for report clarification

## Project Structure

```
fides-project/
├── app.py                        # Main FastAPI application
├── requirements.txt              # Python package dependencies
├── .env                          # Environment variables (API keys)
├── .env.example                  # Environment template (no secrets)
├── .gitignore                    # Git ignore rules
├── README.md                     # This file
├── static/                       # Frontend assets
│   └── style.css                 # Styling and UI themes
└── templates/                    # HTML templates
    └── index.html                # Document upload interface and dashboard
```

## Getting Started

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- API Keys (optional but recommended):
  - **GOOGLE_API_KEY** (Google Gemini) - for entity extraction and chatbot

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/Amarnath10i/FIDES.git
cd FIDES
```

2. **Create and activate a virtual environment**
```bash
python -m venv venv
```

On Windows:
```powershell
venv\Scripts\activate
```

On macOS/Linux:
```bash
source venv/bin/activate
```

3. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**

Copy `.env.example` to `.env` and add your API key:
```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:
```
GOOGLE_API_KEY=your_gemini_api_key_here
```

Get a free key at: https://aistudio.google.com/app/apikey

5. **Start the FastAPI server**
```bash
python app.py
```

The application will be available at: **http://localhost:8000**

## API Endpoints

### Home / Web Interface
**GET** `/`

Serves the interactive web application with document upload and analysis dashboard.

Response: HTML interface with real-time analysis

Example:
```
http://localhost:8000
```

### Health Check Endpoint
**GET** `/api/health`

Verifies service availability and Gemini API status.

Response: JSON with service status, model name, and API readiness

Example:
```bash
curl http://localhost:8000/api/health
```

### Analysis Endpoint
**POST** `/analyze`

Uploads trade documents and performs complete risk assessment.

Request: Multipart form data with `files` (1-5 documents)

Response: JSON object containing:
- Extracted entities (vessel, shipper, consignee, etc.)
- Risk factors and scores
- Federated fingerprint hash
- Executive audit report
- Compliance recommendations

Example:
```bash
curl -X POST \
  -F "files=@bill_of_lading.pdf" \
  -F "files=@invoice.pdf" \
  http://localhost:8000/analyze
```

### Chatbot Endpoint
**POST** `/chat`

Ask the compliance assistant questions about analysis results.

Request: JSON with `question` and `context` fields

Response: Natural language answer from Gemini model

Example:
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"question": "Why is this transaction risky?", "context": {"vessel": "MV STAR", "risk_level": "MEDIUM"}}' \
  http://localhost:8000/chat
```

## Processing Pipeline

FIDES employs a multi-stage processing pipeline for each analysis:

### Stage 1: Document Ingestion
- Parse PDF, PNG, and JPG files
- Extract text using OCR for image-based documents
- Normalize and clean extracted content
- Identify document boundaries and structure

### Stage 2: Entity Extraction
Utilize LLM (Gemini) to identify key entities:
- Organizations and companies
- Individual persons
- Vessel names and identifiers
- Port names and locations
- Invoices and financial amounts

Extract and normalize:
- Entity names and aliases
- Remove duplicate entries
- Cross-reference entities

### Stage 3: Enrichment Processing

Perform comprehensive checks on extracted entities:

1. **Sanctions Screening** - Cross-reference against OFAC and UN sanction lists
2. **AIS Vessel Tracking** - Verify vessel location, flag state, and historical movement
3. **Market Price Benchmarking** - Compare commodity prices against market standards
4. **Address Validation** - Verify corporate addresses in registries
5. **Entity Identity Verification** - Confirm corporate registration data

### Stage 4: Federated Risk Fingerprinting

- Generate cryptographic hash of extracted entities
- Query federated broker network for matching intelligence
- Score cross-broker warnings and alerts
- Flag entities with multiple broker warnings
- Calculate composite risk score

### Stage 5: Report Generation

- Aggregate all risk signals and findings
- Calculate final risk score (0-100 scale)
- Classify risk level: **LOW** | **MEDIUM** | **HIGH** | **CRITICAL**
- Generate human-readable executive brief
- Produce detailed findings and recommendations
- Enable follow-up questions via chatbot

## Configuration

### Environment Variables

Edit `.env` file to configure:

```
# Gemini API Configuration
GOOGLE_API_KEY=your_gemini_api_key_here

# Optional: Specify Gemini model (auto-detected if not set)
# GEMINI_MODEL=gemini-3.5-flash
```

**Note:** The model is automatically detected from available models in your API account. No hardcoding needed.

### Auto-Model Detection

FIDES automatically:
- Detects available Gemini models at startup
- Selects the first model supporting `generateContent`
- Works with any API key/account without code changes

## Supported File Formats

| Format | Support | Implementation |
|--------|---------|-----------------|
| PDF | ✅ Fully supported | Text extraction via PyPDF2 |
| PNG | ✅ Fully supported | OCR via EasyOCR |
| JPG/JPEG | ✅ Fully supported | OCR via EasyOCR |
| WEBP | ✅ Fully supported | OCR via EasyOCR |
| BMP | ✅ Fully supported | OCR via EasyOCR |
| DOCX | ❌ Not supported | Planned for future release |
| XLSX | ❌ Not supported | Planned for future release |

## Testing and Demonstration

### Running the Application

1. Start the server:
```bash
python app.py
```

2. Open http://localhost:8000 in your browser

3. Upload trade documents (PDFs or images)

4. View real-time risk analysis

5. Ask follow-up questions using the compliance chatbot

### Quick Test

Upload sample documents to test:
- Bill of Lading
- Commercial Invoice
- Packing List
- Shipper's Letter of Instruction

The system will extract entities, calculate risk scores, and generate a compliance report within seconds.

## Security and Privacy

### Data Handling
- **File Upload Limit:** Maximum 16 MB per file
- **Temporary Storage:** Uploaded files are stored locally (configure retention policy)
- **API Key Management:** Use `.env` file for credentials (never commit to version control)
- **CORS Configuration:** Currently enabled for development; configure for production

### Best Practices
- ✅ Never commit `.env` file to git (use `.gitignore`)
- ✅ Store API keys securely in environment variables
- ✅ Rotate API keys periodically
- ✅ Enable HTTPS in production
- ✅ Implement automatic file cleanup for uploaded documents

## Troubleshooting

### Issue: "API assistant is unavailable (missing Gemini API key)"

**Solution:** 
1. Verify `.env` file exists and contains `GOOGLE_API_KEY`
2. Restart the server: `python app.py`
3. Check that the API key is valid at https://aistudio.google.com/app/apikey

### Issue: Rate Limit / Quota Exceeded (429 Error)

**Solution:**
- Free tier: Retry after 48 seconds (5 requests/day limit)
- Upgrade to paid plan at: https://ai.google.dev/pricing

### Issue: "No compatible Gemini model found"

**Solution:**
1. Check available models: https://ai.google.dev/models
2. Verify API credentials and access permissions
3. Ensure your Google account has Gemini API enabled

### Issue: OCR not working on image files

**Solution:**
1. Verify image is valid PNG, JPG, WEBP, or BMP format
2. Check image contains readable text
3. Reinstall dependencies: `pip install -r requirements.txt`

### Issue: Port 8000 already in use

**Solution on Windows:**
```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

**Solution on macOS/Linux:**
```bash
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9
```

**Alternative:** Run on different port:
```bash
uvicorn app:app --host 0.0.0.0 --port 8001
```

### Issue: ModuleNotFoundError

**Solution:**
1. Verify virtual environment is activated
2. Reinstall dependencies:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Dependencies

### Core Python Packages

- **fastapi>=0.115.0** - Web framework
- **uvicorn[standard]>=0.30.6** - ASGI server
- **python-multipart>=0.0.9** - File upload handling
- **google-generativeai>=0.8.3** - Gemini API client
- **python-dotenv>=1.0.1** - Environment variable management
- **Pillow>=10.4.0** - Image processing
- **PyPDF2>=3.0.1** - PDF text extraction
- **numpy>=2.1.0** - Numerical computing
- **pandas>=2.3.3** - Data manipulation
- **easyocr>=1.7.2** - Optical character recognition

## License

This project is provided as-is for compliance and risk assessment in international trade.

## Contributing

Contributions are welcome! To contribute:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add feature description"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

Please ensure code follows project conventions and is well-documented.

## Support and Contact

For issues, feature requests, or questions:
- Open an issue on GitHub: https://github.com/Amarnath10i/FIDES/issues
- Check API documentation: https://ai.google.dev/gemini-api/docs

## Additional Resources

- **Gemini API Documentation:** https://ai.google.dev/gemini-api
- **OFAC Sanctions List:** https://ofac.treasury.gov/
- **SWIFT Standards:** https://www.swift.com/
- **Trade Finance Standards:** https://www.iccwbo.org/

---

**Built for compliance and risk management in international trade and shipping** 🚢📋
