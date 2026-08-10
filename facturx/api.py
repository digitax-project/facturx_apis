from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Query, BackgroundTasks
from fastapi.responses import FileResponse, Response
import tempfile
import os
import io
import uvicorn
import logging
from typing import Optional, List
from enum import Enum
from .facturx import (
    get_xml_from_pdf,
    xml_check_xsd,
    generate_from_file,
    extract_any_xml_from_pdf,
    ALL_FILENAMES,  # Import this to see all supported filenames
    FACTURX_FILENAME,
    ZUGFERD_FILENAMES,
    ORDERX_FILENAME
)
from .phase1.api import router as phase1_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("facturx-api")

API_VERSION = "1.0.0"

# Show all recognized XML filenames at startup
logger.info(f"Supported XML filenames: {ALL_FILENAMES}")
logger.info(f"ZUGFeRD filenames: {ZUGFERD_FILENAMES}")

app = FastAPI(
    title="Factur-X API",
    version=API_VERSION,
    description="API for Factur-X PDF generation, XML extraction and validation",
)
app.include_router(phase1_router)

class FlavorEnum(str, Enum):
    facturx = "factur-x"
    orderx = "order-x"
    autodetect = "autodetect"

class LevelEnum(str, Enum):
    # Factur-X levels
    minimum = "minimum"
    basicwl = "basicwl"
    basic = "basic"
    en16931 = "en16931"
    extended = "extended"
    # Order-X levels
    comfort = "comfort"
    # Common value
    autodetect = "autodetect"

class OrderXTypeEnum(str, Enum):
    order = "order"
    order_change = "order_change"
    order_response = "order_response"
    autodetect = "autodetect"

class AFRelationshipEnum(str, Enum):
    data = "data"
    source = "source"
    alternative = "alternative"

@app.post("/facturx-pdfgen", 
          summary="Generate a Factur-X or Order-X PDF", 
          description="Generate a Factur-X or Order-X PDF file from a regular PDF file and an XML file")
async def facturx_pdfgen(
    background_tasks: BackgroundTasks,
    pdf_file: UploadFile = File(..., description="Regular PDF file to be converted"),
    xml_file: UploadFile = File(..., description="Factur-X or Order-X XML file"),
    flavor: FlavorEnum = Form(FlavorEnum.autodetect, description="PDF flavor (Factur-X or Order-X)"),
    level: LevelEnum = Form(LevelEnum.autodetect, description="Compliance level"),
    orderx_type: OrderXTypeEnum = Form(OrderXTypeEnum.autodetect, description="Order-X document type"),
    check_xsd: bool = Form(True, description="Validate XML against XSD"),
    afrelationship: AFRelationshipEnum = Form(AFRelationshipEnum.data, description="AF relationship property"),
    author: Optional[str] = Form(None, description="PDF metadata: Author"),
    title: Optional[str] = Form(None, description="PDF metadata: Title"),
    subject: Optional[str] = Form(None, description="PDF metadata: Subject"),
    keywords: Optional[str] = Form(None, description="PDF metadata: Keywords"),
    lang: Optional[str] = Form(None, description="Language identifier (e.g., en-US)")
):
    pdf_temp_path = None
    xml_temp_path = None
    output_temp_path = None
    
    try:
        # Create temporary files for processing
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_temp, \
             tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as xml_temp, \
             tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as output_temp:
            
            # Save uploaded files to temp files
            pdf_temp.write(await pdf_file.read())
            xml_temp.write(await xml_file.read())
            pdf_temp_path = pdf_temp.name
            xml_temp_path = xml_temp.name
            output_temp_path = output_temp.name
        
        # Create PDF metadata if provided
        pdf_metadata = None
        if any([author, title, subject, keywords]):
            pdf_metadata = {
                'author': author or '',
                'title': title or '',
                'subject': subject or '',
                'keywords': keywords or '',
            }
        
        # Generate Factur-X PDF
        generate_from_file(
            pdf_temp_path, 
            xml_temp_path,
            flavor=flavor,
            level=level,
            orderx_type=orderx_type,
            check_xsd=check_xsd,
            pdf_metadata=pdf_metadata,
            lang=lang,
            output_pdf_file=output_temp_path,
            afrelationship=afrelationship
        )
        
        # Add cleanup to background tasks instead of using background in FileResponse
        files_to_clean = [pdf_temp_path, xml_temp_path]
        background_tasks.add_task(cleanup_temp_files, files_to_clean)
        
        # Return the generated PDF
        return FileResponse(
            path=output_temp_path, 
            media_type="application/pdf",
            filename=f"facturx_{pdf_file.filename}"
        )
        
    except Exception as e:
        # Clean up temp files in case of error
        try:
            if pdf_temp_path and xml_temp_path and output_temp_path:
                cleanup_temp_files([pdf_temp_path, xml_temp_path, output_temp_path])
        except:
            pass
        logger.error(f"Error generating Factur-X PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating Factur-X PDF: {str(e)}")

@app.post("/facturx-pdfextractxml", 
          summary="Extract XML from a Factur-X or Order-X PDF", 
          description="Extract the XML file from a Factur-X or Order-X PDF file")
async def facturx_pdfextractxml(
    background_tasks: BackgroundTasks,
    pdf_file: UploadFile = File(..., description="Factur-X or Order-X PDF file"),
    check_xsd: bool = Form(True, description="Validate extracted XML against XSD"),
    return_xml_file: bool = Form(False, description="Return XML as file instead of text"),
    accept_any_filename: bool = Form(True, description="Extract XML regardless of filename")
):
    temp_path = None
    
    try:
        pdf_content = await pdf_file.read()
        
        # Log info about extraction attempt
        logger.info(f"Attempting to extract XML from {pdf_file.filename}")
        logger.info(f"Returning an XML file: {return_xml_file}")
        logger.info(f"Accept any filename: {accept_any_filename}")
        
        xml_name = None
        xml_content = None
        
        if accept_any_filename:
            # First try with standard filenames
            xml_name, xml_content = get_xml_from_pdf(
                io.BytesIO(pdf_content), 
                check_xsd=check_xsd
            )
            
            # If no XML found, try to extract any embedded file
            if not xml_content:
                logger.info("No standard XML found, attempting to extract any embedded XML file")
                xml_name, xml_content = extract_any_xml_from_pdf(io.BytesIO(pdf_content), check_xsd=check_xsd)
        else:
            # Use default filenames from the library
            xml_name, xml_content = get_xml_from_pdf(
                io.BytesIO(pdf_content), 
                check_xsd=check_xsd
            )
        
        # Check if we found XML
        if not xml_content:
            logger.warning(f"No XML content found in {pdf_file.filename}")
            
            return {
                "success": False,
                "message": "No XML found in the PDF file."
            }
        
        # Log successful extraction
        logger.info(f"Successfully extracted XML: {xml_name}")
        
        # Return as file or text
        if return_xml_file:
            file_name = xml_name or "extracted.xml"
            with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as temp:
                temp_path = temp.name
                temp.write(xml_content)
            
            # Add cleanup to background tasks
            background_tasks.add_task(cleanup_temp_files, [temp_path])
            
            return FileResponse(
                path=temp_path,
                media_type="application/xml",
                filename=file_name
            )
        else:
            return Response(
                content=xml_content,
                media_type="application/xml"
            )
            
    except Exception as e:
        # Clean up temp file in case of error
        try:
            if temp_path:
                cleanup_temp_files([temp_path])
        except:
            pass
        logger.error(f"Error extracting XML: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error extracting XML: {str(e)}")

@app.post("/facturx-xmlcheck", 
          summary="Validate Factur-X or Order-X XML", 
          description="Check a Factur-X or Order-X XML file against the official XML Schema Definition and validate content requirements")
async def facturx_xmlcheck(
    xml_file: UploadFile = File(..., description="Factur-X or Order-X XML file to validate"),
    flavor: FlavorEnum = Form(FlavorEnum.autodetect, description="XML flavor (Factur-X or Order-X)"),
    level: LevelEnum = Form(LevelEnum.autodetect, description="Compliance level"),
    detailed_validation: bool = Form(False, description="Perform detailed field validation beyond XSD schema")
):
    try:
        xml_content = await xml_file.read()
        
        # Basic XSD validation
        result = xml_check_xsd(xml_content, flavor=flavor, level=level)
        
        validation_result = {
            "valid": True,
            "schema_validation": "The XML file is valid against the official XML Schema Definition",
            "profile": "Unknown",
            "details": {}
        }
        
        # Extract profile information
        try:
            from lxml import etree
            from .facturx import get_level, get_flavor, XML_NAMESPACES
            
            xml_root = etree.fromstring(xml_content)
            detected_flavor = get_flavor(xml_root)
            detected_level = get_level(xml_root, flavor=detected_flavor)
            
            validation_result["profile"] = f"{detected_flavor} {detected_level}"
            validation_result["details"]["detected_flavor"] = detected_flavor
            validation_result["details"]["detected_level"] = detected_level
            
            # Add profile-specific information
            namespaces = XML_NAMESPACES.get(detected_flavor, XML_NAMESPACES['factur-x'])
            
            # Extract document information
            doc_id_xpath = xml_root.xpath(
                "//rsm:ExchangedDocument/ram:ID", namespaces=namespaces)
            if doc_id_xpath:
                validation_result["details"]["document_id"] = doc_id_xpath[0].text
                
            # Perform detailed validation if requested
            if detailed_validation:
                validation_issues = validate_facturx_content(xml_root, detected_level, namespaces)
                if validation_issues:
                    validation_result["content_validation_issues"] = validation_issues
                else:
                    validation_result["content_validation"] = "All required fields are present and valid"
            
        except Exception as e:
            validation_result["details"]["profile_detection_error"] = str(e)
        
        return validation_result
        
    except Exception as e:
        logger.error(f"XML validation error: {str(e)}")
        return {
            "valid": False,
            "message": str(e)
        }

def validate_facturx_content(xml_root, level, namespaces):
    """
    Perform detailed content validation based on the Factur-X profile level.
    
    This function checks for mandatory fields based on the profile level.
    
    :param xml_root: XML root element
    :param level: Factur-X profile level (minimum, basicwl, basic, en16931, extended)
    :param namespaces: XML namespaces to use for XPath queries
    :return: List of validation issues or empty list if all valid
    """
    issues = []
    
    # Define fields required by each level
    # The fields are represented as XPath expressions
    required_fields = {
        'minimum': [
            "//ram:ApplicableHeaderTradeSettlement/ram:PaymentReference",  # Payment reference
            "//ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID",  # Seller tax ID
        ],
        'basicwl': [
            "//ram:ApplicableHeaderTradeSettlement/ram:PaymentReference",  # Payment reference
            "//ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID",  # Seller tax ID
            "//ram:BuyerTradeParty/ram:Name",  # Buyer name
        ],
        'basic': [
            "//ram:ApplicableHeaderTradeSettlement/ram:PaymentReference",  # Payment reference
            "//ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID",  # Seller tax ID
            "//ram:BuyerTradeParty/ram:Name",  # Buyer name
            "//ram:ApplicableHeaderTradeDelivery/ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime",  # Delivery date
        ],
        'en16931': [
            "//ram:ApplicableHeaderTradeSettlement/ram:PaymentReference",  # Payment reference
            "//ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID",  # Seller tax ID
            "//ram:BuyerTradeParty/ram:Name",  # Buyer name
            "//ram:ApplicableHeaderTradeDelivery/ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime",  # Delivery date
            "//ram:ApplicableHeaderTradeAgreement/ram:BuyerReference",  # Buyer reference
            "//ram:SpecifiedTradePaymentTerms/ram:Description",  # Payment terms
        ],
        'extended': [
            "//ram:ApplicableHeaderTradeSettlement/ram:PaymentReference",  # Payment reference
            "//ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID",  # Seller tax ID
            "//ram:BuyerTradeParty/ram:Name",  # Buyer name
            "//ram:ApplicableHeaderTradeDelivery/ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime",  # Delivery date
            "//ram:ApplicableHeaderTradeAgreement/ram:BuyerReference",  # Buyer reference
            "//ram:SpecifiedTradePaymentTerms/ram:Description",  # Payment terms
            # Extended profile has additional fields but they're optional
        ]
    }
    
    # Get the required fields based on the level
    # For each level, we include all fields from lower levels too
    fields_to_check = []
    for check_level in ['minimum', 'basicwl', 'basic', 'en16931', 'extended']:
        fields_to_check.extend(required_fields.get(check_level, []))
        if check_level == level:
            break
    
    # Check each required field
    for xpath in fields_to_check:
        elements = xml_root.xpath(xpath, namespaces=namespaces)
        if not elements or not elements[0].text:
            # Get the field name from the XPath (last part after the last slash)
            field_name = xpath.split('/')[-1]
            issues.append(f"Missing or empty required field: {field_name}")
    
    return issues

def cleanup_temp_files(file_paths):
    """Clean up temporary files"""
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.unlink(path)
                logger.debug(f"Cleaned up temporary file: {path}")
        except Exception as e:
            logger.error(f"Error cleaning up file {path}: {str(e)}")

if __name__ == "__main__":
    print("Starting Factur-X API server on http://localhost:6969")
    print("Swagger UI documentation available at http://localhost:6969/docs")
    print("Note: It's recommended to run the API using the run.py script in the root directory")
    uvicorn.run("facturx.api:app", host="0.0.0.0", port=6969, reload=True)
