# KISS Real-World Scenarios - Python

## Table of Contents

- [Introduction](#introduction)
- [Scenario 1: API Client Design](#scenario-1-api-client-design)
- [Scenario 2: Data Processing Pipeline](#scenario-2-data-processing-pipeline)
- [Scenario 3: Configuration Management](#scenario-3-configuration-management)
- [Scenario 4: Error Handling Strategy](#scenario-4-error-handling-strategy)
- [Scenario 5: Testing Approach](#scenario-5-testing-approach)
- [Scenario 6: Code Organization](#scenario-6-code-organization)
- [Migration Guide](#migration-guide)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document presents real-world scenarios where the KISS principle is applied in Python. Each scenario includes a practical problem, analysis of violations, and step-by-step solution with code examples.

---

## Scenario 1: API Client Design

### Context

A Python web application needs to interact with a third-party payment API to process transactions. The team initially designed a comprehensive API client with extensive error handling, retry logic, caching, and response transformation.

### Problem Description

The payment API client became overly complex with multiple layers of abstraction, extensive configuration options, and features that were never used. Developers struggled to understand the code, and adding new endpoints required modifications across multiple files. Simple API calls took hours to implement.

### Analysis of Violations

**Current Issues:**
- **Over-abstraction**: Created abstract base class for single implementation
- **Premature optimization**: Caching implemented before measuring need
- **YAGNI violation**: Features like batch processing, rate limiting, and webhooks built but never used
- **Complex configuration**: 20+ configuration options, most never changed
- **Multiple layers**: Request → Config → Retry → Cache → Transform → Response

**Impact:**
- **Development velocity**: Simple API calls took 2-3 hours instead of 30 minutes
- **Bug frequency**: Complex retry and caching logic introduced subtle bugs
- **Onboarding time**: New developers needed 2-3 days to understand the client
- **Maintenance burden**: Changes required touching multiple files

### BAD Approach

```python
import requests
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
import hashlib

class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"

class AuthType(Enum):
    BEARER = "bearer"
    API_KEY = "api_key"
    BASIC = "basic"

@dataclass
class RetryConfig:
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_multiplier: float = 2.0
    retryable_status_codes: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])

@dataclass
class CacheConfig:
    enabled: bool = True
    ttl_seconds: int = 300
    max_size: int = 1000
    cache_key_prefix: str = "payment_api"

@dataclass
class TransformConfig:
    enabled: bool = True
    snake_to_camel: bool = True
    date_format: str = "iso8601"

@dataclass
class WebhookConfig:
    enabled: bool = False
    endpoint: Optional[str] = None
    secret: Optional[str] = None
    events: List[str] = field(default_factory=list)

@dataclass
class RequestConfig:
    url: str
    method: HttpMethod
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    data: Optional[Dict[str, Any]] = None
    json_data: Optional[Dict[str, Any]] = None
    auth_type: AuthType = AuthType.BEARER
    auth_value: Optional[str] = None
    timeout: float = 30.0
    retry_config: Optional[RetryConfig] = None
    cache_config: Optional[CacheConfig] = None
    transform_config: Optional[TransformConfig] = None
    webhook_config: Optional[WebhookConfig] = None

@dataclass
class Response:
    status_code: int
    data: Any
    headers: Dict[str, str]
    elapsed_time: float
    cached: bool = False
    retry_count: int = 0

class PaymentApiClient(ABC):
    @abstractmethod
    def execute(self, config: RequestConfig) -> Response:
        pass

class PaymentApiClientImpl(PaymentApiClient):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        retry_config: Optional[RetryConfig] = None,
        cache_config: Optional[CacheConfig] = None,
        transform_config: Optional[TransformConfig] = None
    ):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.retry_config = retry_config or RetryConfig()
        self.cache_config = cache_config or CacheConfig()
        self.transform_config = transform_config or TransformConfig()
        self.session = requests.Session()
        self.cache: Dict[str, tuple] = {}
    
    def execute(self, config: RequestConfig) -> Response:
        url = f"{self.base_url}/{config.url.lstrip('/')}"
        headers = {**config.headers}
        
        # Authentication
        if config.auth_type == AuthType.BEARER:
            headers['Authorization'] = f"Bearer {config.auth_value or self.api_key}"
        elif config.auth_type == AuthType.API_KEY:
            headers['X-API-Key'] = config.auth_value or self.api_key
        
        # Cache check
        if config.cache_config and config.cache_config.enabled:
            cache_key = self._generate_cache_key(url, headers, config.params)
            if cache_key in self.cache:
                cached_data, timestamp = self.cache[cache_key]
                if time.time() - timestamp < config.cache_config.ttl_seconds:
                    return Response(
                        status_code=200,
                        data=cached_data,
                        headers={},
                        elapsed_time=0.0,
                        cached=True
                    )
        
        # Retry logic
        last_exception = None
        for attempt in range((config.retry_config or self.retry_config).max_retries + 1):
            try:
                start_time = time.time()
                response = self.session.request(
                    method=config.method.value,
                    url=url,
                    headers=headers,
                    params=config.params,
                    data=config.data,
                    json=config.json_data,
                    timeout=config.timeout
                )
                elapsed = time.time() - start_time
                
                # Check if retryable
                if response.status_code in (config.retry_config or self.retry_config).retryable_status_codes:
                    if attempt < (config.retry_config or self.retry_config).max_retries:
                        time.sleep(config.retry_config.retry_delay * (config.retry_config.backoff_multiplier ** attempt))
                        continue
                
                # Transform response
                data = response.json() if 'application/json' in response.headers.get('content-type', '') else response.text
                if config.transform_config and config.transform_config.enabled:
                    data = self._transform_response(data, config.transform_config)
                
                # Cache successful GET requests
                if config.method == HttpMethod.GET and config.cache_config and config.cache_config.enabled and 200 <= response.status_code < 300:
                    cache_key = self._generate_cache_key(url, headers, config.params)
                    if len(self.cache) < (config.cache_config or self.cache_config).max_size:
                        self.cache[cache_key] = (data, time.time())
                
                result = Response(
                    status_code=response.status_code,
                    data=data,
                    headers=dict(response.headers),
                    elapsed_time=elapsed,
                    retry_count=attempt
                )
                return result
                
            except Exception as e:
                last_exception = e
                if attempt < (config.retry_config or self.retry_config).max_retries:
                    time.sleep(config.retry_config.retry_delay * (config.retry_config.backoff_multiplier ** attempt))
                    continue
                raise last_exception
    
    def _generate_cache_key(self, url: str, headers: Dict, params: Dict) -> str:
        key_data = {'url': url, 'headers': headers, 'params': params}
        return f"{self.cache_config.cache_key_prefix}_{hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()}"
    
    def _transform_response(self, data: Any, config: TransformConfig) -> Any:
        if config.snake_to_camel and isinstance(data, dict):
            return {self._to_camel(k): v for k, v in data.items()}
        return data
    
    def _to_camel(self, snake_str: str) -> str:
        components = snake_str.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])

class PaymentService:
    def __init__(self, client: PaymentApiClient):
        self.client = client
    
    def create_charge(self, amount: float, currency: str, source: str) -> Dict:
        config = RequestConfig(
            url='charges',
            method=HttpMethod.POST,
            json_data={
                'amount': int(amount * 100),  # Convert to cents
                'currency': currency.lower(),
                'source': source
            },
            auth_type=AuthType.API_KEY,
            auth_value=None
        )
        response = self.client.execute(config)
        if 200 <= response.status_code < 300:
            return response.data
        else:
            raise Exception(f"Payment failed: {response.status_code}")
    
    def get_charge(self, charge_id: str) -> Dict:
        config = RequestConfig(
            url=f'charges/{charge_id}',
            method=HttpMethod.GET,
            cache_config=CacheConfig(enabled=True, ttl_seconds=600)
        )
        response = self.client.execute(config)
        if response.status_code == 200:
            return response.data
        else:
            raise Exception(f"Failed to get charge: {response.status_code}")
```

**Why This Approach Fails:**
- 300+ lines for a simple API client
- Complex retry, caching, and transformation logic rarely needed
- Multiple configuration dataclasses that are never customized
- Difficult to add new endpoints (requires understanding complex RequestConfig)
- Cache implementation is memory-intensive and error-prone
- Transform logic is unnecessary (Python dict works fine)

### GOOD Approach

**Solution Strategy:**
1. Remove all unnecessary abstractions and configurations
2. Use requests library directly
3. Implement retry only when actually needed
4. Remove caching (let the API handle it)
5. Remove response transformation
6. Use simple functions for each endpoint

```python
import requests

class PaymentClient:
    """Simple payment API client."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.payment.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({'X-API-Key': api_key})
    
    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make API request and return JSON response."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.request(method, url, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def create_charge(self, amount: float, currency: str, source: str) -> dict:
        """Create a payment charge."""
        return self._request(
            'POST',
            'charges',
            json={
                'amount': int(amount * 100),
                'currency': currency.lower(),
                'source': source
            }
        )
    
    def get_charge(self, charge_id: str) -> dict:
        """Get charge details by ID."""
        return self._request('GET', f'charges/{charge_id}')
    
    def refund_charge(self, charge_id: str, amount: float | None = None) -> dict:
        """Refund a charge, optionally partial."""
        data = {}
        if amount is not None:
            data['amount'] = int(amount * 100)
        return self._request('POST', f'charges/{charge_id}/refunds', json=data)
```

**Benefits:**
- 80% less code (60 lines vs 300+)
- Clear and easy to understand
- Adding new endpoints takes 5 minutes
- No unnecessary complexity
- Easy to test
- Follows requests best practices

### Implementation Steps

1. **Step 1: Analyze Current Usage**
   - Review which features are actually used
   - Identify configuration options that never change
   - Find unused methods and features
   - Document current API endpoints

2. **Step 2: Create Simple Client**
   - Start with basic requests.Session wrapper
   - Implement _request method for common logic
   - Add endpoint methods one at a time
   - Remove all caching and transformation

3. **Step 3: Migrate Callers**
   - Update all code that uses the old client
   - Test each change individually
   - Remove old client after migration complete
   - Update tests

4. **Step 4: Remove Unused Code**
   - Delete old configuration classes
   - Remove unused imports
   - Clean up tests
   - Update documentation

### Testing the Solution

**Test Cases:**
- Test successful charge creation
- Test charge retrieval
- Test refund (full and partial)
- Test error handling (invalid data, network errors)
- Test timeout behavior

**Verification:**
- All existing tests pass
- New tests are simpler
- Code is easier to understand
- Adding new features is faster

---

## Scenario 2: Data Processing Pipeline

### Context

A data science team built an ETL pipeline to process daily sales data from multiple sources into a data warehouse. The initial design used a complex pipeline framework with parallel processing, dependency management, and extensive monitoring.

### Problem Description

The ETL pipeline became over-engineered with a custom framework, complex job scheduling, and unnecessary parallelization for small datasets. Processing 100MB of data took 2 hours, with most time spent in framework overhead. Adding a new data source required creating multiple configuration files and implementing job classes.

### Analysis of Violations

**Current Issues:**
- **Custom framework**: Built a pipeline framework instead of using simple scripts
- **Premature parallelization**: Used multiprocessing for data that fits in memory
- **Over-configuration**: YAML configs for simple transformations
- **Dependency injection**: Complex for simple ETL jobs
- **Unnecessary monitoring**: Detailed metrics for small, fast jobs

**Impact:**
- **Performance**: 2 hours to process 100MB (should take <5 minutes)
- **Development time**: New data source took 2-3 days to add
- **Debugging**: Hard to trace execution through framework
- **Resource usage**: Excessive CPU for small jobs

### BAD Approach

```python
import yaml
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import logging

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class JobMetrics:
    start_time: float
    end_time: Optional[float] = None
    rows_processed: int = 0
    rows_failed: int = 0
    memory_mb: float = 0.0
    cpu_percent: float = 0.0

@dataclass
class JobResult:
    status: JobStatus
    metrics: JobMetrics
    data: Optional[Any] = None
    error: Optional[Exception] = None

@dataclass
class JobDependency:
    job_id: str
    required: bool = True
    condition: Optional[Callable[[JobResult], bool]] = None

@dataclass
class JobConfig:
    job_id: str
    job_type: str
    enabled: bool = True
    parallelizable: bool = True
    max_workers: int = 4
    timeout: float = 3600.0
    retry_on_failure: bool = True
    max_retries: int = 3
    dependencies: List[JobDependency] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)

class PipelineJob(ABC):
    def __init__(self, config: JobConfig):
        self.config = config
        self.metrics: JobMetrics = JobMetrics(start_time=time.time())
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def execute(self) -> JobResult:
        pass
    
    def preprocess(self) -> None:
        pass
    
    def postprocess(self, result: JobResult) -> JobResult:
        return result
    
    def run(self) -> JobResult:
        self.logger.info(f"Starting job {self.config.job_id}")
        self.metrics.start_time = time.time()
        
        try:
            self.preprocess()
            result = self.execute()
            result = self.postprocess(result)
            self.metrics.end_time = time.time()
            result.status = JobStatus.COMPLETED
        except Exception as e:
            self.metrics.end_time = time.time()
            self.logger.error(f"Job failed: {e}")
            result = JobResult(
                status=JobStatus.FAILED,
                metrics=self.metrics,
                error=e
            )
        
        return result

class ExtractJob(PipelineJob):
    def execute(self) -> JobResult:
        import pandas as pd
        
        source_config = self.config.config
        if source_config['type'] == 'csv':
            data = pd.read_csv(source_config['path'])
        elif source_config['type'] == 'database':
            # Complex database connection logic
            pass
        elif source_config['type'] == 'api':
            # API extraction logic
            pass
        
        self.metrics.rows_processed = len(data)
        return JobResult(status=JobStatus.RUNNING, metrics=self.metrics, data=data)

class TransformJob(PipelineJob):
    def execute(self) -> JobResult:
        import pandas as pd
        
        data = self.config.config['input_data']
        transformations = self.config.config['transformations']
        
        for transform in transformations:
            if transform['type'] == 'filter':
                data = data[data[transform['column']] == transform['value']]
            elif transform['type'] == 'map':
                data[transform['column']] = data[transform['column']].map(transform['mapping'])
            elif transform['type'] == 'aggregate':
                data = data.groupby(transform['group_by']).agg(transform['aggregation']).reset_index()
        
        self.metrics.rows_processed = len(data)
        return JobResult(status=JobStatus.RUNNING, metrics=self.metrics, data=data)

class LoadJob(PipelineJob):
    def execute(self) -> JobResult:
        import pandas as pd
        
        data = self.config.config['input_data']
        target_config = self.config.config['target']
        
        if target_config['type'] == 'database':
            # Complex database insertion logic
            pass
        elif target_config['type'] == 'file':
            data.to_csv(target_config['path'], index=False)
        
        self.metrics.rows_processed = len(data)
        return JobResult(status=JobStatus.RUNNING, metrics=self.metrics, data=data)

class PipelineOrchestrator:
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.jobs: Dict[str, PipelineJob] = {}
        self.results: Dict[str, JobResult] = {}
        self.logger = logging.getLogger('PipelineOrchestrator')
    
    def _load_config(self, config_path: str) -> Dict:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _create_job(self, job_config: JobConfig) -> PipelineJob:
        if job_config.job_type == 'extract':
            return ExtractJob(job_config)
        elif job_config.job_type == 'transform':
            return TransformJob(job_config)
        elif job_config.job_type == 'load':
            return LoadJob(job_config)
        else:
            raise ValueError(f"Unknown job type: {job_config.job_type}")
    
    def _check_dependencies(self, job_id: str) -> bool:
        job_config = self.config['jobs'][job_id]
        for dep in job_config['dependencies']:
            if dep['required']:
                dep_result = self.results.get(dep['job_id'])
                if not dep_result or dep_result.status != JobStatus.COMPLETED:
                    return False
        return True
    
    def run(self):
        job_configs = [JobConfig(**jc) for jc in self.config['jobs'].values()]
        
        # Sort by dependencies
        sorted_jobs = self._topological_sort(job_configs)
        
        # Run jobs
        for job_config in sorted_jobs:
            if not job_config.enabled:
                continue
            
            if not self._check_dependencies(job_config.job_id):
                self.logger.warning(f"Skipping {job_config.job_id}: dependencies not met")
                continue
            
            job = self._create_job(job_config)
            
            if job_config.parallelizable and job_config.max_workers > 1:
                with ProcessPoolExecutor(max_workers=job_config.max_workers) as executor:
                    future = executor.submit(job.run)
                    result = future.result(timeout=job_config.timeout)
            else:
                result = job.run()
            
            self.results[job_config.job_id] = result
    
    def _topological_sort(self, jobs: List[JobConfig]) -> List[JobConfig]:
        # Complex topological sort implementation
        # ... implementation details
        return jobs
```

**Why This Approach Fails:**
- Custom framework instead of simple scripts
- Over-parallelized for small datasets
- Complex configuration for simple operations
- Difficult to debug and trace execution
- Poor performance due to framework overhead
- Hard to add new data sources

### GOOD Approach

**Solution Strategy:**
1. Remove custom framework
2. Use simple Python scripts for each ETL job
3. Process data in memory (fits easily)
4. Use pandas directly for transformations
5. Schedule with cron or simple task runner

```python
import pandas as pd
from datetime import datetime

def process_sales_data(input_file: str, output_file: str) -> None:
    """Process daily sales data and save to data warehouse."""
    
    # Extract
    print(f"Loading data from {input_file}")
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} rows")
    
    # Transform
    print("Transforming data")
    df['date'] = pd.to_datetime(df['date'])
    df['total'] = df['quantity'] * df['price']
    
    # Filter invalid records
    df = df[(df['quantity'] > 0) & (df['price'] > 0)]
    
    # Aggregate to daily level
    daily_sales = df.groupby(['date', 'product_id']).agg({
        'quantity': 'sum',
        'total': 'sum'
    }).reset_index()
    
    print(f"Transformed to {len(daily_sales)} daily records")
    
    # Load
    print(f"Saving to {output_file}")
    daily_sales.to_csv(output_file, index=False)
    print("Done!")

def main():
    input_file = f"data/sales/sales_{datetime.now().strftime('%Y%m%d')}.csv"
    output_file = f"warehouse/sales/daily_{datetime.now().strftime('%Y%m%d')}.csv"
    process_sales_data(input_file, output_file)

if __name__ == '__main__':
    main()
```

**Benefits:**
- Processing time: 2 hours → 30 seconds
- Code size: 400+ lines → 40 lines
- Easy to understand and modify
- Simple to add new data sources
- No framework overhead
- Clear execution flow

### Implementation Steps

1. **Step 1: Identify Simple Cases**
   - Find jobs that don't need parallelization
   - Identify jobs that fit in memory
   - Note jobs with simple transformations

2. **Step 2: Create Simple Scripts**
   - Start with one job type at a time
   - Replace framework with direct pandas operations
   - Remove all configuration files
   - Use command-line arguments instead

3. **Step 3: Schedule Jobs**
   - Use cron for daily scheduling
   - Or use Airflow for complex dependencies
   - Simple bash scripts to orchestrate

4. **Step 4: Monitor and Optimize**
   - Add simple logging
   - Monitor performance
   - Only optimize slow jobs

### Testing the Solution

**Test Cases:**
- Test with small sample dataset
- Test with full daily dataset
- Test error handling (missing file, invalid data)
- Test output format

**Verification:**
- Results match old pipeline output
- Performance is significantly better
- Code is easier to maintain
- New data sources can be added quickly

---

## Scenario 3: Configuration Management

### Context

A Python application manages configuration through a complex system with multiple sources, hierarchical overrides, encryption support, and validation. The team spent weeks building a "enterprise-grade" configuration manager.

### Problem Description

The configuration system became overly complex with multiple layers of file loading, environment variable precedence, schema validation, and runtime reloading. Developers struggled to understand where configuration values came from, and adding a new setting required understanding the entire system. Most features (encryption, validation, runtime reload) were never used.

### Analysis of Violations

**Current Issues:**
- **Over-engineering**: Built custom configuration system
- **YAGNI**: Features like encryption and validation never used
- **Complex precedence**: Multiple sources with confusing priority
- **Unnecessary validation**: Schema validation for simple config
- **Runtime reload**: Reload on file change - never needed

**Impact:**
- **Confusion**: Developers don't know where config comes from
- **Debugging**: Hard to trace configuration values
- **Development time**: Adding new config took hours
- **Maintenance**: Complex codebase for simple problem

### BAD Approach

```python
import os
import json
import yaml
import toml
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
import hashlib
import secrets
from cryptography.fernet import Fernet
import threading
from pydantic import BaseModel, validator

class ConfigSource(Enum):
    ENV = "environment"
    FILE = "file"
    DATABASE = "database"
    VAULT = "vault"
    REMOTE = "remote"

class ConfigFormat(Enum):
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"

@dataclass
class ConfigValue:
    value: Any
    source: ConfigSource
    priority: int
    is_encrypted: bool = False
    is_readonly: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ConfigSourceConfig:
    source_type: ConfigSource
    priority: int = 100
    enabled: bool = True
    reload_on_change: bool = False
    config: Dict[str, Any] = field(default_factory=dict)

class ConfigLoader(ABC):
    @abstractmethod
    def load(self) -> Dict[str, Any]:
        pass

class EnvironmentConfigLoader(ConfigLoader):
    def __init__(self, prefix: str = "", priority: int = 100):
        self.prefix = prefix
        self.priority = priority
    
    def load(self) -> Dict[str, Any]:
        return {
            k[len(self.prefix):].lower(): v
            for k, v in os.environ.items()
            if k.startswith(self.prefix)
        }

class FileConfigLoader(ConfigLoader):
    def __init__(self, file_path: str, format: ConfigFormat, priority: int = 200):
        self.file_path = file_path
        self.format = format
        self.priority = priority
    
    def load(self) -> Dict[str, Any]:
        with open(self.file_path, 'r') as f:
            if self.format == ConfigFormat.JSON:
                return json.load(f)
            elif self.format == ConfigFormat.YAML:
                return yaml.safe_load(f)
            elif self.format == ConfigFormat.TOML:
                return toml.load(f)
            else:
                raise ValueError(f"Unknown format: {self.format}")

class DatabaseConfigLoader(ConfigLoader):
    def __init__(self, connection_string: str, table: str, priority: int = 300):
        self.connection_string = connection_string
        self.table = table
        self.priority = priority
    
    def load(self) -> Dict[str, Any]:
        import sqlite3
        conn = sqlite3.connect(self.connection_string)
        cursor = conn.cursor()
        cursor.execute(f"SELECT key, value FROM {self.table}")
        return {row[0]: json.loads(row[1]) for row in cursor.fetchall()}

class ConfigSchema(BaseModel):
    database_url: str
    redis_url: str
    api_key: str
    debug: bool = False
    timeout: int = 30
    max_connections: int = 10
    log_level: str = "INFO"
    
    @validator('timeout')
    def timeout_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('timeout must be positive')
        return v

class ConfigurationManager:
    def __init__(self):
        self.loaders: List[ConfigLoader] = []
        self.values: Dict[str, ConfigValue] = {}
        self.schema: Optional[ConfigSchema] = None
        self.lock = threading.Lock()
        self.encryption_key: Optional[str] = None
        self.watchers: Dict[str, threading.Thread] = {}
    
    def add_loader(self, loader: ConfigLoader):
        with self.lock:
            self.loaders.append(loader)
    
    def set_schema(self, schema: ConfigSchema):
        self.schema = schema
    
    def set_encryption_key(self, key: str):
        self.encryption_key = key
    
    def load_all(self):
        with self.lock:
            # Sort loaders by priority
            sorted_loaders = sorted(self.loaders, key=lambda x: x.priority)
            
            for loader in sorted_loaders:
                data = loader.load()
                for key, value in data.items():
                    config_value = ConfigValue(
                        value=value,
                        source=loader.__class__.__name__,
                        priority=loader.priority,
                        is_encrypted=False
                    )
                    
                    # Only override if higher priority
                    if key not in self.values or config_value.priority > self.values[key].priority:
                        self.values[key] = config_value
            
            # Decrypt encrypted values
            if self.encryption_key:
                self._decrypt_values()
            
            # Validate against schema
            if self.schema:
                self._validate()
    
    def _decrypt_values(self):
        cipher = Fernet(self.encryption_key)
        for key, config_value in self.values.items():
            if config_value.is_encrypted:
                config_value.value = json.loads(cipher.decrypt(config_value.value).decode())
                config_value.is_encrypted = False
    
    def _validate(self):
        try:
            config_dict = {k: v.value for k, v in self.values.items()}
            validated = self.schema(**config_dict)
            for key, value in validated.dict().items():
                self.values[key].value = value
        except Exception as e:
            raise ValueError(f"Configuration validation failed: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, ConfigValue(value=default, source='default', priority=0)).value
    
    def watch_file(self, file_path: str, callback: callable):
        """Watch config file for changes and reload."""
        def watcher():
            last_mtime = os.path.getmtime(file_path)
            while True:
                current_mtime = os.path.getmtime(file_path)
                if current_mtime != last_mtime:
                    self.load_all()
                    callback()
                    last_mtime = current_mtime
                threading.Event().wait(1)
        
        thread = threading.Thread(target=watcher, daemon=True)
        thread.start()
        self.watchers[file_path] = thread

def initialize_config() -> ConfigurationManager:
    """Initialize configuration from all sources."""
    manager = ConfigurationManager()
    
    # Load from environment
    manager.add_loader(EnvironmentConfigLoader(prefix='APP_', priority=100))
    
    # Load from file
    manager.add_loader(FileConfigLoader('config.yaml', ConfigFormat.YAML, priority=200))
    
    # Load from database
    manager.add_loader(DatabaseConfigLoader('config.db', 'config', priority=300))
    
    # Set schema
    manager.set_schema(ConfigSchema())
    
    # Load all
    manager.load_all()
    
    return manager
```

**Why This Approach Fails:**
- 400+ lines for simple configuration
- Multiple loaders, validators, encryption
- Thread watching for file changes (never used)
- Pydantic validation (never caught real errors)
- Confusing priority system
- Hard to add new config values

### GOOD Approach

**Solution Strategy:**
1. Remove all custom configuration code
2. Use environment variables as primary source
3. Optional config file for local development
4. Simple dict for configuration
5. No validation, encryption, or watching

```python
import os
import json
from pathlib import Path
from typing import Any

def load_config(config_file: str | None = None) -> dict:
    """Load configuration from environment variables and optional file."""
    
    # Default configuration
    config = {
        'database_url': os.getenv('DATABASE_URL', 'sqlite:///app.db'),
        'redis_url': os.getenv('REDIS_URL', 'redis://localhost:6379'),
        'api_key': os.getenv('API_KEY', ''),
        'debug': os.getenv('DEBUG', 'false').lower() == 'true',
        'timeout': int(os.getenv('TIMEOUT', '30')),
        'max_connections': int(os.getenv('MAX_CONNECTIONS', '10')),
        'log_level': os.getenv('LOG_LEVEL', 'INFO')
    }
    
    # Override from config file if exists
    if config_file and Path(config_file).exists():
        try:
            file_config = json.loads(Path(config_file).read_text())
            config.update(file_config)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load config file: {e}")
    
    return config

def get_config() -> dict:
    """Get application configuration."""
    return load_config('config.local.json')
```

**Benefits:**
- 95% less code (20 lines vs 400+)
- Clear and predictable (env vars override defaults)
- Easy to add new config values
- No complex system to maintain
- Simple to test
- Follows Python best practices

### Implementation Steps

1. **Step 1: Identify Active Config Values**
   - Review all configuration used in code
   - Document default values
   - Identify which need to be overridden

2. **Step 2: Create Simple Loader**
   - Define default configuration
   - Load from environment variables
   - Optional file override for local dev

3. **Step 3: Migrate Code**
   - Update all config access to use dict
   - Remove config manager imports
   - Update environment variable names if needed

4. **Step 4: Clean Up**
   - Delete complex config system
   - Remove unused config files
   - Update documentation

### Testing the Solution

**Test Cases:**
- Test default configuration
- Test environment variable override
- Test config file override
- Test missing config file (should not fail)
- Test invalid config file (should warn and continue)

**Verification:**
- Configuration values are correct
- Override behavior is predictable
- Easy to add new config values
- Code is much simpler

---

## Scenario 4: Error Handling Strategy

### Context

A Python application had a sophisticated error handling system with custom exception hierarchies, error codes, retry logic, and context tracking. The team wanted "enterprise-grade" error handling.

### Problem Description

The error handling system became overly complex with custom exception classes for every error type, error code registries, and automatic retry mechanisms. Developers had to understand the entire system to add new error handling, and many errors were caught and re-wrapped multiple times, obscuring the root cause.

### Analysis of Violations

**Current Issues:**
- **Over-abstraction**: Custom exception hierarchy for simple errors
- **Error codes**: Mapping exceptions to numeric codes
- **Automatic retry**: Retry logic that often makes things worse
- **Context tracking**: Complex context management
- **Multiple wrapping**: Errors wrapped 3-4 times

**Impact:**
- **Debugging**: Hard to find root cause of errors
- **Development**: Adding error handling requires deep knowledge
- **Confusion**: Multiple exception types for same issue
- **Over-catching**: Errors caught too early

### BAD Approach

```python
import traceback
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import time
from functools import wraps
import logging

class ErrorCode(Enum):
    UNKNOWN_ERROR = "ERR_000"
    VALIDATION_ERROR = "ERR_001"
    DATABASE_ERROR = "ERR_002"
    NETWORK_ERROR = "ERR_003"
    AUTHENTICATION_ERROR = "ERR_004"
    AUTHORIZATION_ERROR = "ERR_005"
    NOT_FOUND_ERROR = "ERR_006"
    CONFLICT_ERROR = "ERR_007"
    RATE_LIMIT_ERROR = "ERR_008"
    TIMEOUT_ERROR = "ERR_009"

class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ErrorContext:
    function_name: str
    line_number: int
    file_name: str
    traceback_str: str
    additional_context: Dict[str, Any] = field(default_factory=dict)

class BaseApplicationError(Exception):
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[ErrorContext] = None,
        user_message: Optional[str] = None
    ):
        super().__init__(message)
        self.error_code = error_code
        self.severity = severity
        self.context = context
        self.user_message = user_message
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'error_code': self.error_code.value,
            'message': str(self),
            'user_message': self.user_message or self.__class__.__name__,
            'severity': self.severity.value,
            'timestamp': self.timestamp
        }

class ValidationError(BaseApplicationError):
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.VALIDATION_ERROR, **kwargs)
        self.field = field

class DatabaseError(BaseApplicationError):
    def __init__(self, message: str, query: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.DATABASE_ERROR, ErrorSeverity.HIGH, **kwargs)
        self.query = query

class NetworkError(BaseApplicationError):
    def __init__(self, message: str, url: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.NETWORK_ERROR, ErrorSeverity.MEDIUM, **kwargs)
        self.url = url

class AuthenticationError(BaseApplicationError):
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCode.AUTHENTICATION_ERROR, ErrorSeverity.HIGH, **kwargs)

class NotFoundError(BaseApplicationError):
    def __init__(self, message: str, resource_type: Optional[str] = None, resource_id: Optional[Any] = None, **kwargs):
        super().__init__(message, ErrorCode.NOT_FOUND_ERROR, **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id

@dataclass
class RetryConfig:
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 10.0
    exponential_backoff: bool = True
    jitter: bool = True
    retryable_exceptions: List[type] = field(default_factory=list)

def with_retry(config: RetryConfig):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = config.initial_delay
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except tuple(config.retryable_exceptions) as e:
                    last_exception = e
                    
                    if attempt < config.max_retries:
                        if config.jitter:
                            import random
                            delay = delay * (0.5 + random.random())
                        
                        time.sleep(min(delay, config.max_delay))
                        
                        if config.exponential_backoff:
                            delay *= 2
                    else:
                        raise
        return wrapper
    return decorator

class ErrorHandler:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.handlers: Dict[ErrorCode, Callable] = {}
    
    def register_handler(self, error_code: ErrorCode, handler: Callable):
        self.handlers[error_code] = handler
    
    def handle(self, error: BaseApplicationError) -> Dict[str, Any]:
        handler = self.handlers.get(error.error_code, self._default_handler)
        return handler(error)
    
    def _default_handler(self, error: BaseApplicationError) -> Dict[str, Any]:
        self.logger.error(
            f"Error {error.error_code.value}: {error}",
            extra={'context': error.context}
        )
        return error.to_dict()

def create_error_context() -> ErrorContext:
    tb = traceback.extract_stack()[-2]
    return ErrorContext(
        function_name=tb.name,
        line_number=tb.lineno,
        file_name=tb.filename,
        traceback_str=traceback.format_exc()
    )

@dataclass
class RetryPolicy:
    max_attempts: int = 3
    backoff_factor: float = 2.0
    status_codes: List[int] = field(default_factory=lambda: [429, 500, 502, 503])

class ApiClient:
    def __init__(self, base_url: str, retry_policy: RetryPolicy = None):
        self.base_url = base_url
        self.retry_policy = retry_policy or RetryPolicy()
        self.error_handler = ErrorHandler(logging.getLogger(__name__))
    
    def make_request(self, endpoint: str, method: str = 'GET', **kwargs) -> Dict[str, Any]:
        for attempt in range(self.retry_policy.max_attempts):
            try:
                response = self._execute_request(endpoint, method, **kwargs)
                
                if response.status_code >= 400:
                    raise self._create_error_from_response(response)
                
                return response.json()
            
            except (NetworkError, DatabaseError) as e:
                if attempt < self.retry_policy.max_attempts - 1:
                    time.sleep(self.retry_policy.backoff_factor ** attempt)
                    continue
                raise
    
    def _execute_request(self, endpoint: str, method: str, **kwargs):
        import requests
        try:
            return requests.request(
                method,
                f"{self.base_url}/{endpoint}",
                timeout=30,
                **kwargs
            )
        except requests.exceptions.RequestException as e:
            context = create_error_context()
            raise NetworkError(
                f"Network error: {str(e)}",
                url=f"{self.base_url}/{endpoint}",
                context=context
            )
    
    def _create_error_from_response(self, response):
        context = create_error_context()
        
        if response.status_code == 401:
            return AuthenticationError(
                "Authentication failed",
                context=context
            )
        elif response.status_code == 404:
            return NotFoundError(
                "Resource not found",
                context=context
            )
        else:
            return BaseApplicationError(
                f"Request failed: {response.status_code}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                context=context
            )
```

**Why This Approach Fails:**
- 400+ lines for error handling
- Custom exception hierarchy for standard errors
- Automatic retry that often fails
- Error codes mapped to numbers
- Complex context tracking
- Errors wrapped multiple times

### GOOD Approach

**Solution Strategy:**
1. Use Python's built-in exceptions
2. Only create custom exceptions for business logic errors
3. No automatic retry (handle explicitly)
4. Simple error messages
5. Let exceptions propagate naturally

```python
class ValidationError(Exception):
    """Raised when input validation fails."""
    pass

class NotFoundError(Exception):
    """Raised when a resource is not found."""
    pass

class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass

import requests

class ApiClient:
    """Simple API client with clear error handling."""
    
    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        if api_key:
            self.session.headers['Authorization'] = f'Bearer {api_key}'
    
    def get(self, endpoint: str) -> dict:
        """Make a GET request."""
        response = self.session.get(f"{self.base_url}/{endpoint}", timeout=30)
        self._check_response(response)
        return response.json()
    
    def post(self, endpoint: str, data: dict) -> dict:
        """Make a POST request."""
        response = self.session.post(f"{self.base_url}/{endpoint}", json=data, timeout=30)
        self._check_response(response)
        return response.json()
    
    def _check_response(self, response: requests.Response):
        """Check response and raise appropriate exceptions."""
        if response.status_code == 401:
            raise AuthenticationError("Invalid API key")
        elif response.status_code == 404:
            raise NotFoundError(f"Resource not found: {response.url}")
        elif response.status_code >= 400:
            raise Exception(f"API error: {response.status_code} - {response.text}")
```

**Benefits:**
- 90% less code (40 lines vs 400+)
- Clear error types
- No automatic retry (explicit is better)
- Easy to understand and extend
- Standard Python exceptions
- Root cause is obvious

### Implementation Steps

1. **Step 1: Identify Necessary Custom Exceptions**
   - Find business logic errors that need specific handling
   - Use built-in exceptions for everything else
   - Remove error codes and contexts

2. **Step 2: Simplify API Client**
   - Remove retry decorator
   - Use simple response checking
   - Raise clear exceptions

3. **Step 3: Update Callers**
   - Catch specific exceptions as needed
   - Let most exceptions propagate
   - Add explicit retry where needed

4. **Step 4: Remove Complex Error System**
   - Delete error handlers and registries
   - Remove context tracking
   - Clean up imports

### Testing the Solution

**Test Cases:**
- Test successful requests
- Test 401 authentication error
- Test 404 not found error
- Test other error status codes
- Test network errors

**Verification:**
- Error messages are clear
- Root cause is obvious
- Easy to add new error handling
- Code is much simpler

---

## Scenario 5: Testing Approach

### Context

A Python application had a sophisticated testing framework with custom test runners, fixtures, data generators, test suites, and extensive mocking infrastructure. The team wanted "comprehensive" testing.

### Problem Description

The testing framework became overly complex with custom test discovery, fixture inheritance, data factories, and extensive mock setups. Writing a simple test required understanding multiple base classes and configuration options. Tests were slow and flaky due to complex fixture setup.

### Analysis of Violations

**Current Issues:**
- **Custom test framework**: Instead of using pytest
- **Complex fixtures**: Multi-level fixture inheritance
- **Data factories**: Over-engineered test data generation
- **Excessive mocking**: Everything was mocked
- **Slow tests**: Complex setup and teardown

**Impact:**
- **Development time**: Writing tests took hours
- **Test reliability**: Flaky tests due to complex setup
- **Onboarding**: Hard to understand test framework
- **Test coverage**: Developers avoided writing tests

### BAD Approach

```python
import unittest
from typing import Dict, Any, List, Callable, Optional, Type
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
import json
from unittest.mock import Mock, patch, MagicMock

class TestLevel(Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"

@dataclass
class TestMetadata:
    level: TestLevel
    description: str
    tags: List[str] = field(default_factory=list)
    timeout: float = 30.0

class BaseTestCase(ABC):
    """Base class for all test cases."""
    
    @abstractmethod
    def setup(self):
        pass
    
    @abstractmethod
    def teardown(self):
        pass
    
    def run_test(self):
        self.setup()
        try:
            self.execute()
        finally:
            self.teardown()
    
    @abstractmethod
    def execute(self):
        pass

@dataclass
class DataFactory:
    """Factory for generating test data."""
    
    @staticmethod
    def create_user(**overrides) -> Dict[str, Any]:
        return {
            'id': 1,
            'name': 'Test User',
            'email': 'test@example.com',
            'created_at': '2024-01-01T00:00:00Z',
            **overrides
        }
    
    @staticmethod
    def create_order(**overrides) -> Dict[str, Any]:
        return {
            'id': 1,
            'user_id': 1,
            'total': 100.0,
            'status': 'pending',
            'created_at': '2024-01-01T00:00:00Z',
            **overrides
        }
    
    @staticmethod
    def create_user_list(count: int, **overrides) -> List[Dict[str, Any]]:
        return [DataFactory.create_user(id=i, **overrides) for i in range(1, count + 1)]

class MockBuilder:
    """Builder for creating complex mocks."""
    
    def __init__(self, mock_class: Type):
        self.mock_class = mock_class
        self.config = {}
    
    def with_return_value(self, value: Any) -> 'MockBuilder':
        self.config['return_value'] = value
        return self
    
    def with_side_effect(self, effect: Callable) -> 'MockBuilder':
        self.config['side_effect'] = effect
        return self
    
    def with_call_count(self, count: int) -> 'MockBuilder':
        self.config['call_count'] = count
        return self
    
    def build(self) -> Mock:
        mock = Mock(spec=self.mock_class)
        for attr, value in self.config.items():
            setattr(mock, attr, value)
        return mock

class TestFixtures:
    """Centralized test fixtures."""
    
    def __init__(self):
        self.users = DataFactory.create_user_list(10)
        self.orders = [DataFactory.create_order(user_id=u['id']) for u in self.users]
        self.mock_db = Mock()
        self.mock_cache = Mock()
        self.mock_logger = Mock()
    
    def setup_database_mocks(self):
        """Setup database mocks with common behavior."""
        def get_user(user_id: int):
            return next((u for u in self.users if u['id'] == user_id), None)
        
        self.mock_db.get_user.side_effect = get_user
        self.mock_db.create_user.side_effect = lambda data: {'id': len(self.users) + 1, **data}
    
    def setup_cache_mocks(self):
        """Setup cache mocks with common behavior."""
        cache_data = {}
        
        def get(key: str):
            return cache_data.get(key)
        
        def set(key: str, value: Any):
            cache_data[key] = value
        
        self.mock_cache.get.side_effect = get
        self.mock_cache.set.side_effect = set

class UserServiceTest(BaseTestCase):
    """Test suite for UserService."""
    
    metadata = TestMetadata(
        level=TestLevel.UNIT,
        description="Tests for UserService"
    )
    
    def setup(self):
        self.fixtures = TestFixtures()
        self.fixtures.setup_database_mocks()
        self.fixtures.setup_cache_mocks()
        self.service = UserService(
            db=self.fixtures.mock_db,
            cache=self.fixtures.mock_cache,
            logger=self.fixtures.mock_logger
        )
    
    def teardown(self):
        self.fixtures = None
        self.service = None
    
    def execute(self):
        self.test_get_user()
        self.test_create_user()
        self.test_get_user_not_found()
    
    def test_get_user(self):
        """Test getting a user by ID."""
        user_id = 1
        user = self.service.get_user(user_id)
        
        assert user is not None
        assert user['id'] == user_id
        assert self.fixtures.mock_db.get_user.called
        self.fixtures.mock_db.get_user.assert_called_once_with(user_id)
    
    def test_create_user(self):
        """Test creating a new user."""
        user_data = DataFactory.create_user(id=None)
        
        with patch.object(self.fixtures.mock_db, 'create_user') as mock_create:
            mock_create.return_value = {'id': 11, **user_data}
            
            user = self.service.create_user(user_data)
            
            assert user is not None
            assert user['id'] == 11
            mock_create.assert_called_once()
    
    def test_get_user_not_found(self):
        """Test getting a user that doesn't exist."""
        with self.assertRaises(NotFoundError):
            self.service.get_user(999)

class IntegrationTestSuite(BaseTestCase):
    """Integration test suite."""
    
    metadata = TestMetadata(
        level=TestLevel.INTEGRATION,
        description="Integration tests"
    )
    
    def setup(self):
        # Setup test database
        # Setup test cache
        # Setup test logger
        pass
    
    def teardown(self):
        # Cleanup test database
        # Cleanup test cache
        pass
    
    def execute(self):
        self.test_full_user_workflow()
    
    def test_full_user_workflow(self):
        """Test complete user creation and retrieval workflow."""
        pass

class TestRunner:
    """Custom test runner."""
    
    def __init__(self):
        self.test_suites: List[BaseTestCase] = []
        self.results: List[Dict[str, Any]] = []
    
    def register_suite(self, suite: Type[BaseTestCase]):
        self.test_suites.append(suite)
    
    def run_all(self):
        for suite_class in self.test_suites:
            suite = suite_class()
            suite.run_test()
            # Collect results
```

**Why This Approach Fails:**
- Custom test framework instead of pytest
- Complex fixture setup
- Data factories for simple test data
- Over-mocking everything
- Hard to write simple tests
- Tests are slow and flaky

### GOOD Approach

**Solution Strategy:**
1. Use pytest as test framework
2. Use simple fixtures for setup
3. Use real objects when possible
4. Mock only external dependencies
5. Keep tests simple and focused

```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_db():
    """Mock database fixture."""
    db = Mock()
    db.get_user.return_value = {'id': 1, 'name': 'Test User', 'email': 'test@example.com'}
    db.create_user.return_value = {'id': 1, 'name': 'New User', 'email': 'new@example.com'}
    return db

@pytest.fixture
def mock_cache():
    """Mock cache fixture."""
    cache = Mock()
    cache.get.return_value = None
    return cache

@pytest.fixture
def user_service(mock_db, mock_cache):
    """User service fixture."""
    return UserService(db=mock_db, cache=mock_cache, logger=Mock())

def test_get_user(user_service, mock_db):
    """Test getting a user."""
    user = user_service.get_user(1)
    
    assert user['id'] == 1
    assert user['name'] == 'Test User'
    mock_db.get_user.assert_called_once_with(1)

def test_get_user_not_found(user_service, mock_db):
    """Test getting a non-existent user."""
    mock_db.get_user.return_value = None
    
    with pytest.raises(NotFoundError):
        user_service.get_user(999)

def test_create_user(user_service, mock_db):
    """Test creating a user."""
    user_data = {'name': 'New User', 'email': 'new@example.com'}
    
    user = user_service.create_user(user_data)
    
    assert user['id'] == 1
    mock_db.create_user.assert_called_once_with(user_data)

@pytest.mark.integration
def test_user_workflow(test_db):
    """Integration test for user workflow."""
    service = UserService(db=test_db, cache=None, logger=None)
    
    # Create user
    user = service.create_user({'name': 'Test', 'email': 'test@example.com'})
    assert user['id'] is not None
    
    # Get user
    retrieved = service.get_user(user['id'])
    assert retrieved['name'] == 'Test'
```

**Benefits:**
- 80% less code
- Uses standard pytest
- Simple fixtures
- Clear test structure
- Fast and reliable
- Easy to understand

### Implementation Steps

1. **Step 1: Install pytest**
   - Remove custom test framework
   - Install pytest and pytest-mock

2. **Step 2: Create Simple Fixtures**
   - Use pytest fixtures for setup
   - Keep fixtures minimal
   - Use conftest.py for shared fixtures

3. **Step 3: Write Simple Tests**
   - Use real objects when possible
   - Mock only external dependencies
   - Keep tests focused

4. **Step 4: Clean Up**
   - Delete custom test framework
   - Remove data factories
   - Update CI/CD to use pytest

### Testing the Solution

**Test Cases:**
- All existing tests work with pytest
- New tests are easier to write
- Tests run faster
- Tests are less flaky

**Verification:**
- pytest discovers all tests
- Test output is clear
- Coverage is maintained or improved
- Development velocity increases

---

## Scenario 6: Code Organization

### Context

A Python web application had a complex directory structure with multiple layers of abstraction, separate packages for every concern, and circular import issues. The team followed "enterprise" patterns.

### Problem Description

The codebase was over-organized with too many packages and modules, leading to import confusion and difficulty finding code. Simple changes required touching multiple files, and developers struggled to understand the code structure.

### Analysis of Violations

**Current Issues:**
- **Over-packaging**: Too many small packages
- **Deep nesting**: Files buried deep in directory structure
- **Circular imports**: Complex interdependencies
- **Separation gone wrong**: Related code split across packages
- **Interface overload**: Too many abstractions

**Impact:**
- **Navigation**: Hard to find code
- **Changes**: Simple fixes require many files
- **Imports**: Confusing import paths
- **Onboarding**: Difficult to learn structure

### BAD Approach

```
app/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── base_config.py
│   │   ├── app_config.py
│   │   ├── database_config.py
│   │   └── cache_config.py
│   ├── exceptions/
│   │   ├── __init__.py
│   │   ├── base_exception.py
│   │   ├── validation_exception.py
│   │   └── not_found_exception.py
│   └── logging/
│       ├── __init__.py
│       └── logger.py
├── interfaces/
│   ├── __init__.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base_repository.py
│   │   └── user_repository_interface.py
│   └── services/
│       ├── __init__.py
│       ├── base_service.py
│       └── user_service_interface.py
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── user_entity.py
│   │   └── order_entity.py
│   ├── value_objects/
│   │   ├── __init__.py
│   │   ├── email.py
│   │   └── money.py
│   └── aggregates/
│       ├── __init__.py
│       └── user.py
├── application/
│   ├── __init__.py
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── create_user_command.py
│   │   └── update_user_command.py
│   ├── queries/
│   │   ├── __init__.py
│   │   ├── get_user_query.py
│   │   └── list_users_query.py
│   └── handlers/
│       ├── __init__.py
│       ├── command_handler.py
│       └── query_handler.py
├── infrastructure/
│   ├── __init__.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py
│   │   │   └── session.py
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── user_repository.py
│   │   │   └── order_repository.py
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── user_model.py
│   │       └── order_model.py
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── redis_client.py
│   │   └── cache_manager.py
│   └── external/
│       ├── __init__.py
│       ├── api_client.py
│       └── email_service.py
├── presentation/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── controllers/
│   │   │   ├── __init__.py
│   │   │   ├── user_controller.py
│   │   │   └── order_controller.py
│   │   ├── dto/
│   │   │   ├── __init__.py
│   │   │   ├── user_dto.py
│   │   │   └── order_dto.py
│   │   ├── validators/
│   │   │   ├── __init__.py
│   │   │   └── user_validator.py
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── auth_middleware.py
│   │       └── error_middleware.py
│   └── cli/
│       ├── __init__.py
│       └── commands.py
└── shared/
    ├── __init__.py
    ├── utils/
    │   ├── __init__.py
    │   ├── date_utils.py
    │   └── string_utils.py
    └── constants/
        ├── __init__.py
        └── error_codes.py
```

### GOOD Approach

**Solution Strategy:**
1. Flatten directory structure
2. Group related functionality
3. Remove unnecessary abstractions
4. Keep imports simple
5. Follow Python package conventions

```
app/
├── __init__.py
├── config.py
├── database.py
├── models/
│   ├── __init__.py
│   ├── user.py
│   └── order.py
├── repositories/
│   ├── __init__.py
│   ├── user.py
│   └── order.py
├── services/
│   ├── __init__.py
│   ├── user.py
│   └── order.py
├── api/
│   ├── __init__.py
│   ├── users.py
│   └── orders.py
└── utils/
    ├── __init__.py
    └── helpers.py
```

```python
# config.py
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///app.db')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'

# database.py
import sqlite3
from contextlib import contextmanager

def get_connection():
    return sqlite3.connect(DATABASE_URL)

@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

# models/user.py
from dataclasses import dataclass

@dataclass
class User:
    id: int
    name: str
    email: str

# repositories/user.py
from models import User

def get_user(db, user_id: int) -> User | None:
    cursor = db.cursor()
    cursor.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    return User(*row) if row else None

def create_user(db, name: str, email: str) -> User:
    cursor = db.cursor()
    cursor.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
    db.commit()
    return User(id=cursor.lastrowid, name=name, email=email)

# services/user.py
from repositories import user as user_repo

def get_user(db, user_id: int) -> User:
    user = user_repo.get_user(db, user_id)
    if not user:
        raise NotFoundError(f"User {user_id} not found")
    return user

# api/users.py
from flask import Flask, request, jsonify
from database import get_db
from services import user as user_service

app = Flask(__name__)

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id: int):
    with get_db() as db:
        user = user_service.get_user(db, user_id)
        return jsonify({'id': user.id, 'name': user.name, 'email': user.email})
```

**Benefits:**
- Clear structure
- Easy to find code
- Simple imports
- Related code together
- No circular imports
- Easy to onboard

### Implementation Steps

1. **Step 1: Map Current Structure**
   - Document current file locations
   - Identify related code
   - Note circular dependencies

2. **Step 2: Design New Structure**
   - Group by feature, not layer
   - Flatten deep nesting
   - Remove unnecessary packages

3. **Step 3: Refactor Incrementally**
   - Move one package at a time
   - Update imports
   - Fix circular dependencies

4. **Step 4: Clean Up**
   - Remove old directories
   - Update documentation
   - Run all tests

### Testing the Solution

**Test Cases:**
- All imports work correctly
- No circular dependencies
- Tests still pass
- Easy to find code

**Verification:**
- Code is easier to navigate
- Changes are faster
- New developers onboard quickly
- Structure is clear

---

## Migration Guide

### Refactoring Existing Codebases

When refactoring existing Python code to follow KISS:

1. **Phase 1: Assessment**
   - Identify violations using tools (pylint, radon, vulture)
   - Prioritize by impact and complexity
   - Document current state
   - Gather metrics (code size, test coverage, performance)

2. **Phase 2: Planning**
   - Create refactoring roadmap
   - Design new architecture
   - Plan incremental changes
   - Define success criteria

3. **Phase 3: Implementation**
   - Implement changes incrementally
   - Add comprehensive tests
   - Maintain backwards compatibility where possible
   - Run tests after each change

4. **Phase 4: Verification**
   - Run all tests
   - Measure improvements
   - Update documentation
   - Get team feedback

### Incremental Refactoring Strategies

**Strategy 1: Boy Scout Rule**
- Description: Leave code better than you found it
- When to use: During regular development
- Example: Simplify a function while fixing a bug

**Strategy 2: Strangler Fig Pattern**
- Description: Replace old code gradually by intercepting calls
- When to use: Large, complex systems
- Example: Route new features to simple code, old to complex, migrate over time

**Strategy 3: Branch by Abstraction**
- Description: Create abstraction layer, move implementation, remove layer
- When to use: When you need both old and new during transition
- Example: Create simple interface, migrate callers, remove old implementation

### Common Refactoring Patterns

1. **Replace Conditional with Polymorphism**
   - Description: Use polymorphism instead of complex if/else chains
   - Helps apply KISS: Simplifies complex conditional logic

2. **Extract Method**
   - Description: Pull out code into separate methods
   - Helps apply KISS: Makes functions smaller and focused

3. **Replace Magic Numbers with Constants**
   - Description: Give meaningful names to numbers
   - Helps apply KISS: Makes code self-documenting

4. **Replace Nested Conditional with Guard Clauses**
   - Description: Return early instead of deep nesting
   - Helps apply KISS: Reduces cognitive load

### Testing During Refactoring

**Regression Testing:**
- Run full test suite after each change
- Use pytest for test execution
- Ensure no regressions introduced
- Test edge cases

**Integration Testing:**
- Test that refactored code integrates with rest of system
- Verify no breaking changes to external interfaces
- Test performance characteristics
- Tools: pytest, coverage.py

---

## Language-Specific Notes

### Common Real-World Challenges in Python

- **Framework dogma**: Following Django/Flask/FastAPI patterns where simple code would work
- **Import confusion**: Over-packaging makes imports complex
- **Static typing overuse**: Complex type hints that add no value
- **Async overuse**: Using async/await where it's not needed
- **Class overuse**: Creating classes when functions suffice

### Framework-Specific Scenarios

- **Django**: Overusing signals, excessive middleware, complex queryset chaining
- **Flask**: Over-engineering with blueprints for simple apps
- **FastAPI**: Over-complicating dependency injection, unnecessary router organization
- **Celery**: Creating complex task chains for simple jobs

### Ecosystem Tools

**Refactoring Tools:**
- **rope**: Advanced Python refactoring
- **black**: Code formatting (enforces simplicity)
- **isort**: Import organization
- **autoflake**: Remove unused imports

**Analysis Tools:**
- **pylint**: Complexity analysis
- **flake8**: Style and complexity
- **radon**: Code metrics
- **vulture**: Dead code detection
- **mypy**: Type checking

### Best Practices for Python

1. **Use built-ins**: Leverage Python's rich standard library
2. **Prefer functions**: Use functions over classes when possible
3. **Context managers**: Use `with` for resource management
4. **List comprehensions**: Use for simple transformations
5. **Type hints**: Use for clarity, not complexity
6. **Docstrings**: Document why, not what

### Case Studies

**Case Study 1: E-commerce Platform Refactoring**
- Context: 200,000+ line codebase, complex architecture
- Problem: New features took weeks, bugs were common
- Solution: Simplified from 8-layer architecture to 3-layer
- Results: Feature time reduced 60%, bug rate down 40%

**Case Study 2: Data Processing Pipeline**
- Context: Custom ETL framework for small datasets
- Problem: Processing took hours, hard to maintain
- Solution: Replaced with simple pandas scripts
- Results: Processing time 2 hours → 5 minutes, code 80% smaller

**Case Study 3: API Service**
- Context: Over-engineered REST API client
- Problem: Simple calls were complex and slow
- Solution: Used requests directly with simple wrapper
- Results: Code 90% smaller, latency reduced 50%
