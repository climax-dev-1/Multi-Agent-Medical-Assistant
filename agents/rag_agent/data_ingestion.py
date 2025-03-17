import os
import json
import logging
from pathlib import Path
import pandas as pd
from typing import List, Dict, Any, Optional, Union
# from unstructured.partition.pdf import partition_pdf
# from unstructured.chunking.title import chunk_by_title
from PyPDF2 import PdfReader

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MedicalDataIngestion:
    """
    Handles ingestion of various medical data formats into the RAG system.
    """
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the data ingestion pipeline.
        
        Args:
            config_path: Optional path to configuration file
        """
        # Initialize stats
        self.stats = {
            "files_processed": 0,
            "documents_ingested": 0,
            "errors": 0
        }
        
        # For simplicity, we'll just log instead of integrating with RAG system
        logger.info("MedicalDataIngestion initialized")
    
    def ingest_directory(self, directory_path: str, file_extension: Optional[str] = None) -> Dict[str, Any]:
        """
        Ingest all files in a directory.
        
        Args:
            directory_path: Path to directory containing files
            file_extension: Optional file extension filter (e.g., ".txt", ".pdf")
            
        Returns:
            Dictionary with ingestion statistics
        """
        logger.info(f"Processing directory: {directory_path}")
        
        try:
            directory = Path(directory_path)
            if not directory.exists() or not directory.is_dir():
                raise ValueError(f"Directory does not exist: {directory_path}")
            
            # Get all files with the specified extension
            if file_extension:
                files = list(directory.glob(f"*{file_extension}"))
            else:
                files = [f for f in directory.iterdir() if f.is_file()]
            
            logger.info(f"Found {len(files)} files to process")
            
            for file_path in files:
                try:
                    self.ingest_file(str(file_path))
                    self.stats["files_processed"] += 1
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")
                    self.stats["errors"] += 1
            
            return self.stats
            
        except Exception as e:
            logger.error(f"Error processing directory: {e}")
            return self.stats
    
    def ingest_file(self, file_path: str) -> Dict[str, Any]:
        """
        Ingest a single file based on its extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with ingestion results
        """
        logger.info(f"Processing file: {file_path}")
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Handle different file formats
        if file_path.suffix.lower() == '.txt':
            return self._ingest_text_file(file_path)
        elif file_path.suffix.lower() == '.csv':
            return self._ingest_csv_file(file_path)
        elif file_path.suffix.lower() == '.json':
            return self._ingest_json_file(file_path)
        elif file_path.suffix.lower() == '.pdf':
            return self._ingest_pdf_file(file_path)
        else:
            logger.warning(f"Unsupported file format: {file_path.suffix}")
            return {"success": False, "error": "Unsupported file format"}
    
    def _ingest_text_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Ingest a plain text file.
        
        Args:
            file_path: Path to the text file
            
        Returns:
            Dictionary with ingestion results
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract metadata from filename
            metadata = {
                "source": file_path.name,
                "file_type": "txt"
            }
            
            # Create document object
            document = {
                "content": content,
                "metadata": metadata
            }
            
            logger.info(f"Successfully ingested text file: {file_path}")
            self.stats["documents_ingested"] += 1
            
            return {"success": True, "document": document}
            
        except Exception as e:
            logger.error(f"Error ingesting text file: {e}")
            return {"success": False, "error": str(e)}
    
    def _ingest_csv_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Ingest a CSV file, treating each row as a separate document.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            Dictionary with ingestion results
        """
        try:
            df = pd.read_csv(file_path)
            
            # Find the column with the most text content
            text_column = self._identify_content_column(df)
            
            documents = []
            for _, row in df.iterrows():
                # Extract content from identified column
                content = str(row[text_column])
                
                # Extract metadata from other columns
                metadata = {
                    "source": file_path.name,
                    "file_type": "csv"
                }
                
                # Add all other columns as metadata
                for col in df.columns:
                    if col != text_column and not pd.isna(row[col]):
                        metadata[col] = str(row[col])
                
                documents.append({
                    "content": content,
                    "metadata": metadata
                })
            
            logger.info(f"Successfully ingested CSV file with {len(documents)} entries: {file_path}")
            self.stats["documents_ingested"] += len(documents)
            
            return {"success": True, "documents": documents}
            
        except Exception as e:
            logger.error(f"Error ingesting CSV file: {e}")
            return {"success": False, "error": str(e)}
    
    def _ingest_json_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Ingest a JSON file.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            Dictionary with ingestion results
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            documents = []
            
            # Handle different JSON structures
            if isinstance(data, list):
                # List of documents
                for item in data:
                    # Check if item has required fields
                    if isinstance(item, dict):
                        # Try to identify content field
                        content_field = self._identify_json_content_field(item)
                        if content_field:
                            content = item[content_field]
                            
                            # Use remaining fields as metadata
                            metadata = {
                                "source": file_path.name,
                                "file_type": "json"
                            }
                            
                            for key, value in item.items():
                                if key != content_field and isinstance(value, (str, int, float, bool)):
                                    metadata[key] = value
                            
                            documents.append({
                                "content": content,
                                "metadata": metadata
                            })
            elif isinstance(data, dict):
                # Single document or dictionary of documents
                for key, value in data.items():
                    if isinstance(value, str) and len(value) > 100:
                        # This looks like content
                        documents.append({
                            "content": value,
                            "metadata": {
                                "source": file_path.name,
                                "file_type": "json",
                                "key": key
                            }
                        })
                    elif isinstance(value, dict):
                        # Nested document
                        content_field = self._identify_json_content_field(value)
                        if content_field:
                            content = value[content_field]
                            
                            # Use remaining fields as metadata
                            metadata = {
                                "source": file_path.name,
                                "file_type": "json",
                                "document_id": key
                            }
                            
                            for k, v in value.items():
                                if k != content_field and isinstance(v, (str, int, float, bool)):
                                    metadata[k] = v
                            
                            documents.append({
                                "content": content,
                                "metadata": metadata
                            })
            
            if not documents:
                logger.warning(f"No valid documents found in JSON file: {file_path}")
                return {"success": False, "error": "No valid documents found"}
            
            logger.info(f"Successfully ingested JSON file with {len(documents)} entries: {file_path}")
            self.stats["documents_ingested"] += len(documents)
            
            return {"success": True, "documents": documents}
            
        except Exception as e:
            logger.error(f"Error ingesting JSON file: {e}")
            return {"success": False, "error": str(e)}
    
    # def _ingest_pdf_file(self, file_path: Path) -> Dict[str, Any]:
    #     """
    #     Ingest a PDF file.
        
    #     Args:
    #         file_path: Path to the PDF file
            
    #     Returns:
    #         Dictionary with ingestion results
    #     """
    #     try:
    #         # For simplicity, we'll just log that we would extract text
    #         logger.info(f"Would extract text from PDF: {file_path}")
            
    #         # In a real implementation, you would use a library like PyPDF2 or pdfplumber
    #         # For now, we'll just create a placeholder document
    #         document = {
    #             "content": f"[PDF content would be extracted from {file_path.name}]",
    #             "metadata": {
    #                 "source": file_path.name,
    #                 "file_type": "pdf"
    #             }
    #         }
            
    #         logger.info(f"Successfully processed PDF file: {file_path}")
    #         self.stats["documents_ingested"] += 1
            
    #         return {"success": True, "document": document}
            
    #     except Exception as e:
    #         logger.error(f"Error ingesting PDF file: {e}")
    #         return {"success": False, "error": str(e)}

    # def _ingest_pdf_file(self, file_path: Path) -> Dict[str, Any]:
    #     """
    #     Ingest a PDF file using unstructured.io, which provides advanced document parsing capabilities.
        
    #     Args:
    #         file_path: Path to the PDF file
            
    #     Returns:
    #         Dictionary with ingestion results
    #     """
    #     try:
    #         # # Try to import unstructured
    #         # try:
    #         #     from unstructured.partition.pdf import partition_pdf
    #         #     from unstructured.chunking.title import chunk_by_title
    #         # except ImportError:
    #         #     logger.error("unstructured is not installed. Please install it using: pip install unstructured")
    #         #     return {"success": False, "error": "unstructured library not found"}
                
    #         # Extract elements from PDF
    #         elements = partition_pdf(
    #             file_path,
    #             # Additional parameters:
    #             extract_images_in_pdf=False,  # Set to True to extract images
    #             extract_tables=True,  # Extract tables from the PDF
    #             infer_table_structure=True,  # Try to infer structure of tables
    #             chunking_strategy="by_title"  # Chunk elements by title hierarchy
    #         )
            
    #         # Process different element types
    #         content_parts = []
    #         tables = []
    #         images = []
    #         metadata_parts = {}
            
    #         for element in elements:
    #             if hasattr(element, "category"):
    #                 # Add text with category context
    #                 element_text = str(element)
    #                 element_category = element.category
                    
    #                 if element_category == "Title":
    #                     content_parts.append(f"\n## {element_text}\n")
    #                 elif element_category == "NarrativeText":
    #                     content_parts.append(element_text)
    #                 elif element_category == "ListItem":
    #                     content_parts.append(f"- {element_text}")
    #                 elif element_category == "Table":
    #                     content_parts.append(f"\n[TABLE]\n{element_text}\n[/TABLE]\n")
    #                     if hasattr(element, "metadata") and element.metadata:
    #                         tables.append({
    #                             "text": element_text,
    #                             "metadata": element.metadata.__dict__ if hasattr(element.metadata, "__dict__") else element.metadata
    #                         })
    #                 elif element_category == "Image":
    #                     content_parts.append(f"\n[IMAGE: {element_text}]\n")
    #                     if hasattr(element, "metadata") and element.metadata:
    #                         images.append({
    #                             "text": element_text,
    #                             "metadata": element.metadata.__dict__ if hasattr(element.metadata, "__dict__") else element.metadata
    #                         })
    #                 else:
    #                     content_parts.append(element_text)
                    
    #                 # Collect metadata from elements
    #                 if hasattr(element, "metadata") and element.metadata:
    #                     metadata = element.metadata.__dict__ if hasattr(element.metadata, "__dict__") else element.metadata
    #                     for key, value in metadata.items():
    #                         if key not in metadata_parts:
    #                             metadata_parts[key] = value
            
    #         # Combine content parts
    #         content = "\n".join(content_parts)
            
    #         # Create consolidated metadata
    #         metadata = {
    #             "source": file_path.name,
    #             "file_type": "pdf",
    #             "has_tables": len(tables) > 0,
    #             "table_count": len(tables),
    #             "has_images": len(images) > 0,
    #             "image_count": len(images)
    #         }
            
    #         # Add extracted metadata
    #         metadata.update(metadata_parts)
            
    #         # Create document object with structured elements
    #         document = {
    #             "content": content,
    #             "metadata": metadata,
    #             "tables": tables,
    #             "images": images,
    #             "elements": [{"category": getattr(e, "category", "Unknown"), "text": str(e)} for e in elements]
    #         }
            
    #         logger.info(f"Successfully ingested PDF file using unstructured.io: {file_path}")
    #         self.stats["documents_ingested"] += 1
            
    #         return {"success": True, "document": document}
                
    #     except Exception as e:
    #         logger.error(f"Error ingesting PDF file with unstructured.io: {e}")
    #         return {"success": False, "error": str(e)}

    def _ingest_pdf_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Ingest a PDF file using PyPDF2.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dictionary with ingestion results
        """
        try:
            # # Try to import PyPDF2
            # try:
            #     from PyPDF2 import PdfReader
            # except ImportError:
            #     logger.error("PyPDF2 is not installed. Please install it using: pip install PyPDF2")
            #     return {"success": False, "error": "PyPDF2 library not found"}
                
            # Open the PDF file
            reader = PdfReader(file_path)
            
            # Extract text from all pages
            content = ""
            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    content += f"--- Page {page_num + 1} ---\n{page_text}\n\n"
            
            # Extract metadata from the document info
            metadata = {
                "source": file_path.name,
                "file_type": "pdf",
                "num_pages": len(reader.pages)
            }
            
            # Try to extract additional metadata from the PDF
            if reader.metadata:
                for key, value in reader.metadata.items():
                    if key and value and isinstance(value, str):
                        # Remove the leading slash in metadata keys (e.g., "/Author" → "Author")
                        clean_key = key[1:] if key.startswith("/") else key
                        metadata[clean_key.lower()] = value
            
            # Create document object
            document = {
                "content": content,
                "metadata": metadata
            }
            
            logger.info(f"Successfully ingested PDF file with {len(reader.pages)} pages: {file_path}")
            self.stats["documents_ingested"] += 1

            # print("########### PRINTED FROM data_ingestion/_ingest_pdf_file: document:", document)
            
            return {"success": True, "document": document}
            
        except Exception as e:
            logger.error(f"Error ingesting PDF file: {e}")
            return {"success": False, "error": str(e)}
    
    def _identify_content_column(self, df: pd.DataFrame) -> str:
        """
        Identify which column in a DataFrame contains the main content.
        
        Args:
            df: Pandas DataFrame
            
        Returns:
            Name of the content column
        """
        # Look for columns with these names
        content_column_names = ["content", "text", "description", "abstract", "body"]
        
        for name in content_column_names:
            if name in df.columns:
                return name
        
        # If no standard content column found, look for the column with longest strings
        avg_lengths = {}
        for col in df.columns:
            if df[col].dtype == 'object':  # Only check string columns
                # Calculate average string length
                avg_length = df[col].astype(str).apply(len).mean()
                avg_lengths[col] = avg_length
        
        if avg_lengths:
            # Return column with longest average string length
            return max(avg_lengths.items(), key=lambda x: x[1])[0]
        
        # Fallback to first column
        return df.columns[0]
    
    def _identify_json_content_field(self, item: Dict) -> Optional[str]:
        """
        Identify which field in a JSON object contains the main content.
        
        Args:
            item: Dictionary representing a JSON object
            
        Returns:
            Name of the content field or None if not found
        """
        # Look for fields with these names
        content_field_names = ["content", "text", "description", "abstract", "body"]
        
        for name in content_field_names:
            if name in item and isinstance(item[name], str):
                return name
        
        # If no standard content field found, look for the field with longest string
        text_fields = {}
        for key, value in item.items():
            if isinstance(value, str) and len(value) > 50:
                text_fields[key] = len(value)
        
        if text_fields:
            # Return field with longest text
            return max(text_fields.items(), key=lambda x: x[1])[0]
        
        return None