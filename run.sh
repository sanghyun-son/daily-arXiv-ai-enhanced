#!/bin/bash

# Local testing script with date range support
# Usage: ./run.sh [OPTIONS]
# Options:
#   --range START_DATE END_DATE    Process papers from START_DATE to END_DATE (YYYY-MM-DD format)
#   --crawl                        Crawl data only (skip AI processing and conversion)
#   --process                      Process existing data only (skip crawling)
#   --help                         Show this help message

set -e  # Exit on any error

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --range START_DATE END_DATE    Process papers from START_DATE to END_DATE (YYYY-MM-DD format)"
    echo "  --crawl                        Crawl data only (skip AI processing and conversion)"
    echo "  --process                      Process existing data only (skip crawling)"
    echo "  --help                         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --crawl                                    # Crawl today's papers"
    echo "  $0 --process                                  # Process existing data for today"
    echo "  $0 --range 2024-01-01 2024-01-07 --crawl     # Crawl papers from Jan 1-7, 2024"
    echo "  $0 --range 2024-01-01 2024-01-07 --process   # Process existing data from Jan 1-7, 2024"
    echo ""
    echo "Note: Due to batch processing nature, you must choose either --crawl or --process"
    echo "      Crawl first, then process later when batch jobs are complete"
}

# Function to validate date format
validate_date() {
    local date=$1
    if [[ ! $date =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        echo "Error: Invalid date format. Use YYYY-MM-DD (e.g., 2024-01-01)"
        exit 1
    fi
    
    # Check if date is valid using date command
    if ! date -d "$date" >/dev/null 2>&1; then
        echo "Error: Invalid date: $date"
        exit 1
    fi
}

# Function to generate date range
generate_date_range() {
    local start_date=$1
    local end_date=$2
    
    local current_date=$start_date
    local dates=()
    
    # Convert dates to timestamps for proper comparison
    local start_timestamp=$(date -d "$start_date" +%s)
    local end_timestamp=$(date -d "$end_date" +%s)
    local current_timestamp=$start_timestamp
    
    while [[ $current_timestamp -le $end_timestamp ]]; do
        local date_str=$(date -d "@$current_timestamp" +%Y-%m-%d)
        dates+=("$date_str")
        current_timestamp=$((current_timestamp + 86400))  # Add 1 day in seconds
    done
    
    # Return the array by setting a global variable
    DATES_ARRAY=("${dates[@]}")
}

# Parse command line arguments
MODE=""
START_DATE=""
END_DATE=""
CUSTOM_RANGE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --range)
            if [[ $# -lt 3 ]]; then
                echo "Error: --range requires START_DATE and END_DATE arguments"
                exit 1
            fi
            START_DATE=$2
            END_DATE=$3
            validate_date "$START_DATE"
            validate_date "$END_DATE"
            CUSTOM_RANGE=true
            shift 3
            ;;
        --crawl)
            if [[ -n "$MODE" ]]; then
                echo "Error: Cannot specify both --crawl and --process"
                exit 1
            fi
            MODE="crawl"
            shift
            ;;
        --process)
            if [[ -n "$MODE" ]]; then
                echo "Error: Cannot specify both --crawl and --process"
                exit 1
            fi
            MODE="process"
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option $1"
            show_usage
            exit 1
            ;;
    esac
done

# Check that a mode was specified
if [[ -z "$MODE" ]]; then
    echo "Error: Must specify either --crawl or --process"
    show_usage
    exit 1
fi

# Environment variables check
echo "=== Environment Check ==="

if [[ "$MODE" == "process" ]]; then
    # For processing, we need OpenAI API key
    if [ -z "$OPENAI_API_KEY" ]; then
        echo "❌ Error: OPENAI_API_KEY is required for processing mode"
        echo "Please set: export OPENAI_API_KEY=\"your-api-key-here\""
        exit 1
    fi
    echo "✅ OPENAI_API_KEY is set"
else
    # For crawling, API key is optional
    if [ -z "$OPENAI_API_KEY" ]; then
        echo "⚠️  Warning: OPENAI_API_KEY not set (not needed for crawling)"
    else
        echo "✅ OPENAI_API_KEY is set"
    fi
fi

# Set default values
export LANGUAGE=${LANGUAGE:-"Korean"}
export CATEGORIES=${CATEGORIES:-"cs.AI,cs.CL,cs.CV,cs.DC,cs.IR,cs.LG,cs.MA"}
export MODEL_NAME=${MODEL_NAME:-"gpt-5-mini"}
export OPENAI_BASE_URL=${OPENAI_BASE_URL:-"https://api.openai.com/v1"}
export INTERESTS=${INTERESTS:-"Video Understanding,Foundation Models,Distributed Training,Large Language Models,Vision Language Models,Video Dataset"}

echo "🔧 Configuration:"
echo "   MODE: $MODE"
echo "   LANGUAGE: $LANGUAGE"
echo "   CATEGORIES: $CATEGORIES"
echo "   MODEL_NAME: $MODEL_NAME"
echo "   OPENAI_BASE_URL: $OPENAI_BASE_URL"
echo "   INTERESTS: $INTERESTS"

# Determine date range to process
if [[ "$CUSTOM_RANGE" == "true" ]]; then
    echo "📅 Processing custom date range: $START_DATE to $END_DATE"
    generate_date_range "$START_DATE" "$END_DATE"
    DATES=("${DATES_ARRAY[@]}")
else
    today=$(date -u "+%Y-%m-%d")
    echo "📅 Processing today's papers: $today"
    DATES=("$today")
fi

echo ""
echo "=== Starting $MODE Workflow ==="
echo "📅 Dates to process: ${DATES[*]}"
# Process each date in the range
for date in "${DATES[@]}"; do
    echo ""
    echo "=== Processing date: $date ==="
    
    if [[ "$MODE" == "crawl" ]]; then
        # CRAWL MODE: Crawl data only
        echo "Step 1: Checking for existing data for $date..."
        
        # Check if date's file already exists
        if [ -f "data/${date}.jsonl" ]; then
            echo "📁 Found existing file for $date, skipping crawl..."
        else
            echo "📝 No existing file found, starting crawl for $date..."
            
            cd daily_arxiv
            scrapy crawl arxiv -o ../data/${date}.jsonl
            
            if [ ! -f "../data/${date}.jsonl" ]; then
                echo "❌ Crawling failed for $date, no data file generated"
                exit 1
            fi
            echo "✅ Crawling completed for $date"
            cd ..
        fi
        
        # Check duplicates
        echo "Step 2: Performing intelligent deduplication check for $date..."
        python daily_arxiv/daily_arxiv/check_stats.py --date $date
        dedup_exit_code=$?
        
        case $dedup_exit_code in
            0)
                echo "✅ Deduplication check passed for $date"
                ;;
            1)
                echo "⏭️  Skipping $date - no new content"
                continue
                ;;
            2)
                echo "❌ Error in deduplication for $date"
                exit 2
                ;;
            *)
                echo "❌ Unknown exit code for $date, stopping..."
                exit 1
                ;;
        esac
        
        # Submit batch job for AI processing
        echo "Step 3: Submitting batch job for AI processing for $date..."
        cd ai
        
        # Check if batch was already submitted
        if [ -f "../data/${date}_batch_submitted.txt" ]; then
            echo "📁 Batch job already submitted for $date, skipping..."
            cd ..
        else
            echo "📤 Submitting batch job for AI processing..."
            python submit_batch.py --data ../data/${date}.jsonl
            
            if [ $? -ne 0 ]; then
                echo "❌ Batch job submission failed for $date"
                exit 1
            fi
            
            # Create a marker file to indicate batch job is submitted
            echo "$(date -u)" > "../data/${date}_batch_submitted.txt"
            echo "✅ Batch job submitted successfully for $date"
            cd ..
        fi
        
    elif [[ "$MODE" == "process" ]]; then
        # PROCESS MODE: Process existing data only
        echo "Step 1: Checking for existing data for $date..."
        
        if [ ! -f "data/${date}.jsonl" ]; then
            echo "❌ No data file found for $date: data/${date}.jsonl"
            echo "   Please run crawl mode first: ./run.sh --crawl --range $date $date"
            exit 1
        fi
        
        echo "✅ Found data file for $date"
        
        # AI processing
        echo "Step 2: AI enhancement processing for $date..."
        cd ai
        
        # Check if batch job was submitted
        if [ ! -f "../data/${date}_batch_submitted.txt" ]; then
            echo "❌ No batch job found for $date"
            echo "   Please run crawl mode first: ./run.sh --crawl --range $date $date"
            exit 1
        fi
        
        # Process batch results (wait for completion)
        echo "⏳ Processing batch results for $date..."
        python process_batch.py --data ../data/${date}.jsonl --wait
        
        if [ $? -ne 0 ]; then
            echo "❌ Batch processing failed for $date"
            exit 1
        fi
        echo "✅ AI enhancement processing completed for $date"
        cd ..
        
        # Convert to Markdown
        echo "Step 3: Converting to Markdown for $date..."
        cd to_md
        
        AI_FILE="../data/${date}_AI_enhanced_${LANGUAGE}.jsonl"
        if [ -f "$AI_FILE" ]; then
            echo "📄 Using AI enhanced data for conversion..."
            python convert.py --data "$AI_FILE"
            
            if [ $? -ne 0 ]; then
                echo "❌ Markdown conversion failed for $date"
                exit 1
            fi
            echo "✅ Markdown conversion completed for $date"
        else
            echo "❌ Error: AI enhanced file not found for $date"
            echo "AI file: $AI_FILE"
            exit 1
        fi
        cd ..
    fi
    
    echo "✅ Completed $MODE for $date"
done

# Update file list (always run)
echo ""
echo "Step 4: Updating file list..."
ls data/*.jsonl | sed 's|data/||' > assets/file-list.txt
echo "✅ File list updated"

# Completion summary
echo ""
echo "=== Workflow Completed ==="
if [[ "$CUSTOM_RANGE" == "true" ]]; then
    echo "📅 Processed date range: $START_DATE to $END_DATE"
fi

if [[ "$MODE" == "crawl" ]]; then
    echo "🔄 Crawl workflow finished:"
    echo "   ✅ Data crawling"
    echo "   ✅ Smart duplicate check"
    echo "   ✅ Batch job submission"
    echo "   ✅ File list update"
    echo ""
    echo "💡 Next step: Run processing when batch jobs are complete:"
    echo "   ./run.sh --process --range $START_DATE $END_DATE"
elif [[ "$MODE" == "process" ]]; then
    echo "🎉 Process workflow finished:"
    echo "   ✅ AI enhancement"
    echo "   ✅ Markdown conversion"
    echo "   ✅ File list update"
fi
