# ISP Examples - Python

## Table of Contents

- [Introduction](#introduction)
- [Example 1: Smart Device Control](#example-1-smart-device-control)
- [Example 2: File System Operations](#example-2-file-system-operations)
- [Example 3: Event Listeners](#example-3-event-listeners)
- [Example 4: Data Repository](#example-4-data-repository)
- [Example 5: Payment Processing](#example-5-payment-processing)
- [Example 6: Worker Interface](#example-6-worker-interface)
- [Example 7: Multimedia Player](#example-7-multimedia-player)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document provides paired examples of BAD and GOOD implementations of the ISP (Interface Segregation Principle) principle in Python. Each example demonstrates a common violation and the corrected implementation.

## Example 1: Smart Device Control

### BAD Example: Monolithic Smart Device Interface

```python
class SmartDevice:
    def turn_on(self):
        pass

    def turn_off(self):
        pass

    def connect_to_wifi(self):
        pass

    def connect_to_bluetooth(self):
        pass

    def set_brightness(self, level):
        pass

    def set_volume(self, level):
        pass

    def change_channel(self, channel):
        pass

    def play_audio(self):
        pass

    def play_video(self):
        pass

    def record(self):
        pass


class SmartBulb(SmartDevice):
    def turn_on(self):
        print("Bulb on")

    def turn_off(self):
        print("Bulb off")

    def set_brightness(self, level):
        print(f"Brightness: {level}")

    def connect_to_wifi(self):
        raise NotImplementedError("Not supported")

    def connect_to_bluetooth(self):
        raise NotImplementedError("Not supported")

    def set_volume(self, level):
        raise NotImplementedError("Not supported")

    def change_channel(self, channel):
        raise NotImplementedError("Not supported")

    def play_audio(self):
        raise NotImplementedError("Not supported")

    def play_video(self):
        raise NotImplementedError("Not supported")

    def record(self):
        raise NotImplementedError("Not supported")


class SmartTV(SmartDevice):
    def turn_on(self):
        print("TV on")

    def turn_off(self):
        print("TV off")

    def set_brightness(self, level):
        print(f"Brightness: {level}")

    def set_volume(self, level):
        print(f"Volume: {level}")

    def change_channel(self, channel):
        print(f"Channel: {channel}")

    def play_audio(self):
        print("Playing audio")

    def play_video(self):
        print("Playing video")

    def record(self):
        print("Recording")

    def connect_to_wifi(self):
        print("Connected to WiFi")

    def connect_to_bluetooth(self):
        raise NotImplementedError("Not supported")
```

**Problems:**
- SmartBulb forced to implement 8 unsupported methods
- Interfaces are bloated with irrelevant methods
- Many NotImplementedError thrown
- Difficult to understand what each device actually does

### GOOD Example: Segregated Device Interfaces

```python
from abc import ABC, abstractmethod


class Powerable(ABC):
    @abstractmethod
    def turn_on(self):
        pass

    @abstractmethod
    def turn_off(self):
        pass


class WiFiConnectable(ABC):
    @abstractmethod
    def connect_to_wifi(self):
        pass


class BrightnessControl(ABC):
    @abstractmethod
    def set_brightness(self, level):
        pass


class VolumeControl(ABC):
    @abstractmethod
    def set_volume(self, level):
        pass


class MediaPlayer(ABC):
    @abstractmethod
    def play_audio(self):
        pass

    @abstractmethod
    def play_video(self):
        pass


class Recorder(ABC):
    @abstractmethod
    def record(self):
        pass


class SmartBulb(Powerable, BrightnessControl):
    def turn_on(self):
        print("Bulb on")

    def turn_off(self):
        print("Bulb off")

    def set_brightness(self, level):
        print(f"Brightness: {level}")


class SmartTV(Powerable, BrightnessControl, VolumeControl, MediaPlayer, Recorder, WiFiConnectable):
    def turn_on(self):
        print("TV on")

    def turn_off(self):
        print("TV off")

    def set_brightness(self, level):
        print(f"Brightness: {level}")

    def set_volume(self, level):
        print(f"Volume: {level}")

    def play_audio(self):
        print("Playing audio")

    def play_video(self):
        print("Playing video")

    def record(self):
        print("Recording")

    def connect_to_wifi(self):
        print("Connected to WiFi")
```

**Improvements:**
- Each device implements only relevant interfaces
- No unnecessary methods or exceptions
- Clear, focused interfaces
- Easy to understand device capabilities

### Explanation

The BAD example creates a monolithic interface that all smart devices must implement, forcing SmartBulb to implement 8 methods it doesn't support. The GOOD example splits the functionality into focused interfaces (Powerable, BrightnessControl, MediaPlayer, etc.), allowing each device to implement only what it needs.

---

## Example 2: File System Operations

### BAD Example: All File Operations in One Interface

```python
class FileOperations:
    def exists(self, path):
        pass

    def is_file(self, path):
        pass

    def is_directory(self, path):
        pass

    def read_bytes(self, path):
        pass

    def read_text(self, path):
        pass

    def write_bytes(self, path, data):
        pass

    def write_text(self, path, text):
        pass

    def create_directory(self, path):
        pass

    def delete_directory(self, path):
        pass

    def list_files(self, path):
        pass

    def compress(self, path):
        pass

    def decompress(self, path):
        pass

    def encrypt(self, path, key):
        pass

    def decrypt(self, path, key):
        pass


class SimpleFileSystem(FileOperations):
    def exists(self, path):
        return True

    def is_file(self, path):
        return True

    def is_directory(self, path):
        return False

    def read_bytes(self, path):
        return b"data"

    def read_text(self, path):
        return "text"

    def write_bytes(self, path, data):
        pass

    def write_text(self, path, text):
        pass

    def create_directory(self, path):
        raise NotImplementedError("Not supported")

    def delete_directory(self, path):
        raise NotImplementedError("Not supported")

    def list_files(self, path):
        raise NotImplementedError("Not supported")

    def compress(self, path):
        raise NotImplementedError("Not supported")

    def decompress(self, path):
        raise NotImplementedError("Not supported")

    def encrypt(self, path, key):
        raise NotImplementedError("Not supported")

    def decrypt(self, path, key):
        raise NotImplementedError("Not supported")
```

**Problems:**
- SimpleFileSystem forced to implement 6 unsupported methods
- Interface has 15 unrelated operations
- Not clear which operations are actually supported
- Clients depend on entire interface for simple needs

### GOOD Example: Segregated File Interfaces

```python
from abc import ABC, abstractmethod


class FileExistence(ABC):
    @abstractmethod
    def exists(self, path):
        pass

    @abstractmethod
    def is_file(self, path):
        pass

    @abstractmethod
    def is_directory(self, path):
        pass


class FileReader(ABC):
    @abstractmethod
    def read_bytes(self, path):
        pass

    @abstractmethod
    def read_text(self, path):
        pass


class FileWriter(ABC):
    @abstractmethod
    def write_bytes(self, path, data):
        pass

    @abstractmethod
    def write_text(self, path, text):
        pass


class DirectoryManager(ABC):
    @abstractmethod
    def create_directory(self, path):
        pass

    @abstractmethod
    def delete_directory(self, path):
        pass

    @abstractmethod
    def list_files(self, path):
        pass


class Compressor(ABC):
    @abstractmethod
    def compress(self, path):
        pass

    @abstractmethod
    def decompress(self, path):
        pass


class Encryptor(ABC):
    @abstractmethod
    def encrypt(self, path, key):
        pass

    @abstractmethod
    def decrypt(self, path, key):
        pass


class SimpleFileSystem(FileExistence, FileReader, FileWriter):
    def exists(self, path):
        return True

    def is_file(self, path):
        return True

    def is_directory(self, path):
        return False

    def read_bytes(self, path):
        return b"data"

    def read_text(self, path):
        return "text"

    def write_bytes(self, path, data):
        pass

    def write_text(self, path, text):
        pass


class CompleteFileSystem(FileExistence, FileReader, FileWriter, DirectoryManager, Compressor, Encryptor):
    def exists(self, path):
        return True

    def is_file(self, path):
        return True

    def is_directory(self, path):
        return False

    def read_bytes(self, path):
        return b"data"

    def read_text(self, path):
        return "text"

    def write_bytes(self, path, data):
        pass

    def write_text(self, path, text):
        pass

    def create_directory(self, path):
        pass

    def delete_directory(self, path):
        pass

    def list_files(self, path):
        return []

    def compress(self, path):
        pass

    def decompress(self, path):
        pass

    def encrypt(self, path, key):
        pass

    def decrypt(self, path, key):
        pass
```

**Improvements:**
- SimpleFileSystem only implements relevant interfaces
- Interfaces are focused and cohesive
- No unnecessary exceptions
- Clear separation of concerns

### Explanation

The BAD example creates a massive FileOperations interface with 15 methods mixing concerns. SimpleFileSystem must implement 6 unsupported methods. The GOOD example splits operations into focused interfaces (FileExistence, FileReader, FileWriter, etc.), allowing different implementations to choose relevant capabilities.

---

## Example 3: Event Listeners

### BAD Example: Fat Event Listener Interface

```python
class EventListener:
    def on_click(self):
        pass

    def on_double_click(self):
        pass

    def on_right_click(self):
        pass

    def on_mouse_over(self):
        pass

    def on_mouse_out(self):
        pass

    def on_key_press(self):
        pass

    def on_key_up(self):
        pass

    def on_load(self):
        pass

    def on_unload(self):
        pass

    def on_error(self):
        pass


class Button(EventListener):
    def on_click(self):
        print("Button clicked")

    def on_double_click(self):
        print("Button double-clicked")

    def on_right_click(self):
        raise NotImplementedError("Not supported")

    def on_mouse_over(self):
        raise NotImplementedError("Not supported")

    def on_mouse_out(self):
        raise NotImplementedError("Not supported")

    def on_key_press(self):
        raise NotImplementedError("Not supported")

    def on_key_up(self):
        raise NotImplementedError("Not supported")

    def on_load(self):
        raise NotImplementedError("Not supported")

    def on_unload(self):
        raise NotImplementedError("Not supported")

    def on_error(self):
        raise NotImplementedError("Not supported")


class Page(EventListener):
    def on_load(self):
        print("Page loaded")

    def on_unload(self):
        print("Page unloaded")

    def on_error(self):
        print("Error occurred")

    def on_click(self):
        raise NotImplementedError("Not supported")

    def on_double_click(self):
        raise NotImplementedError("Not supported")

    def on_right_click(self):
        raise NotImplementedError("Not supported")

    def on_mouse_over(self):
        raise NotImplementedError("Not supported")

    def on_mouse_out(self):
        raise NotImplementedError("Not supported")

    def on_key_press(self):
        raise NotImplementedError("Not supported")

    def on_key_up(self):
        raise NotImplementedError("Not supported")
```

**Problems:**
- Button and Page forced to implement irrelevant methods
- Interface mixes unrelated event types
- Many exceptions thrown for unsupported events
- Not clear what each component actually handles

### GOOD Example: Segregated Event Interfaces

```python
from abc import ABC, abstractmethod


class ClickListener(ABC):
    @abstractmethod
    def on_click(self):
        pass


class DoubleClickListener(ABC):
    @abstractmethod
    def on_double_click(self):
        pass


class MouseEventListener(ABC):
    @abstractmethod
    def on_mouse_over(self):
        pass

    @abstractmethod
    def on_mouse_out(self):
        pass


class KeyListener(ABC):
    @abstractmethod
    def on_key_press(self):
        pass

    @abstractmethod
    def on_key_up(self):
        pass


class LifecycleListener(ABC):
    @abstractmethod
    def on_load(self):
        pass

    @abstractmethod
    def on_unload(self):
        pass

    @abstractmethod
    def on_error(self):
        pass


class Button(ClickListener, DoubleClickListener):
    def on_click(self):
        print("Button clicked")

    def on_double_click(self):
        print("Button double-clicked")


class Page(LifecycleListener):
    def on_load(self):
        print("Page loaded")

    def on_unload(self):
        print("Page unloaded")

    def on_error(self):
        print("Error occurred")


class InteractiveButton(ClickListener, DoubleClickListener, MouseEventListener):
    def on_click(self):
        print("Button clicked")

    def on_double_click(self):
        print("Button double-clicked")

    def on_mouse_over(self):
        print("Mouse over button")

    def on_mouse_out(self):
        print("Mouse out of button")
```

**Improvements:**
- Each component implements only relevant event interfaces
- No unnecessary exceptions
- Clear separation of event types
- Easy to add new event capabilities

### Explanation

The BAD example creates a monolithic EventListener interface with 10 methods for all event types. Button only needs click handling but must implement 8 unsupported methods. The GOOD example segregates events by type (Click, Mouse, Key, Lifecycle), allowing each component to implement only what it needs.

---

## Example 4: Data Repository

### BAD Example: All CRUD Operations

```python
class DataRepository:
    def create(self, entity):
        pass

    def read(self, id):
        pass

    def update(self, entity):
        pass

    def delete(self, id):
        pass

    def find_all(self):
        pass

    def find_by_criteria(self, criteria):
        pass

    def batch_create(self, entities):
        pass

    def batch_update(self, entities):
        pass

    def batch_delete(self, ids):
        pass

    def cache(self, entity):
        pass

    def from_cache(self, id):
        pass

    def clear_cache(self):
        pass

    def begin_transaction(self):
        pass

    def commit_transaction(self):
        pass

    def rollback_transaction(self):
        pass


class ReadOnlyRepository(DataRepository):
    def read(self, id):
        print(f"Reading {id}")

    def find_all(self):
        print("Finding all")

    def find_by_criteria(self, criteria):
        print(f"Finding by {criteria}")

    def create(self, entity):
        raise NotImplementedError("Read-only")

    def update(self, entity):
        raise NotImplementedError("Read-only")

    def delete(self, id):
        raise NotImplementedError("Read-only")

    def batch_create(self, entities):
        raise NotImplementedError("Read-only")

    def batch_update(self, entities):
        raise NotImplementedError("Read-only")

    def batch_delete(self, ids):
        raise NotImplementedError("Read-only")

    def cache(self, entity):
        raise NotImplementedError("Not supported")

    def from_cache(self, id):
        raise NotImplementedError("Not supported")

    def clear_cache(self):
        raise NotImplementedError("Not supported")

    def begin_transaction(self):
        raise NotImplementedError("Not supported")

    def commit_transaction(self):
        raise NotImplementedError("Not supported")

    def rollback_transaction(self):
        raise NotImplementedError("Not supported")
```

**Problems:**
- ReadOnlyRepository must implement 11 unsupported methods
- Interface mixes CRUD, batch, cache, and transactions
- Large, unfocused interface
- Unclear what each repository actually supports

### GOOD Example: Segregated Repository Interfaces

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List

T = TypeVar('T')
ID = TypeVar('ID')


class Repository(ABC, Generic[T, ID]):
    @abstractmethod
    def create(self, entity: T):
        pass

    @abstractmethod
    def read(self, id: ID) -> T:
        pass

    @abstractmethod
    def update(self, entity: T):
        pass

    @abstractmethod
    def delete(self, id: ID):
        pass


class Searchable(ABC, Generic[T, ID]):
    @abstractmethod
    def find_all(self) -> List[T]:
        pass

    @abstractmethod
    def find_by_criteria(self, criteria) -> List[T]:
        pass


class Batchable(ABC, Generic[T, ID]):
    @abstractmethod
    def batch_create(self, entities: List[T]):
        pass

    @abstractmethod
    def batch_update(self, entities: List[T]):
        pass

    @abstractmethod
    def batch_delete(self, ids: List[ID]):
        pass


class Cacheable(ABC, Generic[T, ID]):
    @abstractmethod
    def cache(self, entity: T):
        pass

    @abstractmethod
    def from_cache(self, id: ID) -> T:
        pass

    @abstractmethod
    def clear_cache(self):
        pass


class Transactional(ABC):
    @abstractmethod
    def begin_transaction(self):
        pass

    @abstractmethod
    def commit_transaction(self):
        pass

    @abstractmethod
    def rollback_transaction(self):
        pass


class ReadOnlyRepository(Searchable):
    def find_all(self):
        print("Finding all")
        return []

    def find_by_criteria(self, criteria):
        print(f"Finding by {criteria}")
        return []


class FullRepository(Repository, Searchable, Batchable, Cacheable, Transactional):
    def create(self, entity):
        print(f"Creating {entity}")

    def read(self, id):
        print(f"Reading {id}")
        return None

    def update(self, entity):
        print(f"Updating {entity}")

    def delete(self, id):
        print(f"Deleting {id}")

    def find_all(self):
        print("Finding all")
        return []

    def find_by_criteria(self, criteria):
        print(f"Finding by {criteria}")
        return []

    def batch_create(self, entities):
        print(f"Batch creating {len(entities)} entities")

    def batch_update(self, entities):
        print(f"Batch updating {len(entities)} entities")

    def batch_delete(self, ids):
        print(f"Batch deleting {len(ids)} entities")

    def cache(self, entity):
        print(f"Caching {entity}")

    def from_cache(self, id):
        print(f"From cache: {id}")
        return None

    def clear_cache(self):
        print("Cache cleared")

    def begin_transaction(self):
        print("Transaction began")

    def commit_transaction(self):
        print("Transaction committed")

    def rollback_transaction(self):
        print("Transaction rolled back")
```

**Improvements:**
- Interfaces focused on single responsibilities
- ReadOnlyRepository only implements relevant Searchable
- Clear capabilities for each repository type
- Easy to mix and match interfaces

### Explanation

The BAD example creates a monolithic DataRepository with 15 methods mixing concerns. ReadOnlyRepository must implement 11 unsupported methods. The GOOD example splits into focused interfaces (Repository, Searchable, Batchable, Cacheable, Transactional), allowing each repository to choose its capabilities.

---

## Example 5: Payment Processing

### BAD Example: All Payment Methods

```python
class PaymentMethod:
    def charge(self, amount):
        pass

    def refund(self, transaction_id):
        pass

    def authorize(self, amount):
        pass

    def capture(self, authorization_id):
        pass

    def void(self, authorization_id):
        pass

    def get_transaction_status(self, transaction_id):
        pass

    def get_refund_status(self, refund_id):
        pass

    def create_recurring_payment(self, schedule):
        pass

    def cancel_recurring_payment(self, payment_id):
        pass

    def update_payment_method(self, payment_id, new_method):
        pass


class CashPayment(PaymentMethod):
    def charge(self, amount):
        print(f"Charging cash: ${amount}")

    def refund(self, transaction_id):
        print(f"Refunding cash: {transaction_id}")

    def get_transaction_status(self, transaction_id):
        return "completed"

    def authorize(self, amount):
        raise NotImplementedError("Cash doesn't authorize")

    def capture(self, authorization_id):
        raise NotImplementedError("Cash doesn't capture")

    def void(self, authorization_id):
        raise NotImplementedError("Cash doesn't void")

    def get_refund_status(self, refund_id):
        raise NotImplementedError("Not supported")

    def create_recurring_payment(self, schedule):
        raise NotImplementedError("Cash can't be recurring")

    def cancel_recurring_payment(self, payment_id):
        raise NotImplementedError("Cash can't be recurring")

    def update_payment_method(self, payment_id, new_method):
        raise NotImplementedError("Not supported")


class CreditCardPayment(PaymentMethod):
    def charge(self, amount):
        print(f"Charging card: ${amount}")

    def refund(self, transaction_id):
        print(f"Refunding card: {transaction_id}")

    def authorize(self, amount):
        print(f"Authorizing: ${amount}")

    def capture(self, authorization_id):
        print(f"Capturing: {authorization_id}")

    def void(self, authorization_id):
        print(f"Voiding: {authorization_id}")

    def get_transaction_status(self, transaction_id):
        return "completed"

    def get_refund_status(self, refund_id):
        return "completed"

    def create_recurring_payment(self, schedule):
        print(f"Creating recurring payment: {schedule}")

    def cancel_recurring_payment(self, payment_id):
        print(f"Cancelling recurring payment: {payment_id}")

    def update_payment_method(self, payment_id, new_method):
        print(f"Updating payment method: {payment_id}")
```

**Problems:**
- CashPayment must implement 7 unsupported methods
- Interface mixes basic operations with advanced features
- Not clear what each payment method supports
- Unnecessary complexity for simple payment types

### GOOD Example: Segregated Payment Interfaces

```python
from abc import ABC, abstractmethod


class BasicPayment(ABC):
    @abstractmethod
    def charge(self, amount):
        pass

    @abstractmethod
    def refund(self, transaction_id):
        pass


class AuthorizablePayment(ABC):
    @abstractmethod
    def authorize(self, amount):
        pass

    @abstractmethod
    def capture(self, authorization_id):
        pass

    @abstractmethod
    def void(self, authorization_id):
        pass


class TrackablePayment(ABC):
    @abstractmethod
    def get_transaction_status(self, transaction_id):
        pass

    @abstractmethod
    def get_refund_status(self, refund_id):
        pass


class RecurringPayment(ABC):
    @abstractmethod
    def create_recurring_payment(self, schedule):
        pass

    @abstractmethod
    def cancel_recurring_payment(self, payment_id):
        pass


class UpdatablePayment(ABC):
    @abstractmethod
    def update_payment_method(self, payment_id, new_method):
        pass


class CashPayment(BasicPayment):
    def charge(self, amount):
        print(f"Charging cash: ${amount}")

    def refund(self, transaction_id):
        print(f"Refunding cash: {transaction_id}")


class CreditCardPayment(BasicPayment, AuthorizablePayment, TrackablePayment, RecurringPayment, UpdatablePayment):
    def charge(self, amount):
        print(f"Charging card: ${amount}")

    def refund(self, transaction_id):
        print(f"Refunding card: {transaction_id}")

    def authorize(self, amount):
        print(f"Authorizing: ${amount}")

    def capture(self, authorization_id):
        print(f"Capturing: {authorization_id}")

    def void(self, authorization_id):
        print(f"Voiding: {authorization_id}")

    def get_transaction_status(self, transaction_id):
        return "completed"

    def get_refund_status(self, refund_id):
        return "completed"

    def create_recurring_payment(self, schedule):
        print(f"Creating recurring payment: {schedule}")

    def cancel_recurring_payment(self, payment_id):
        print(f"Cancelling recurring payment: {payment_id}")

    def update_payment_method(self, payment_id, new_method):
        print(f"Updating payment method: {payment_id}")
```

**Improvements:**
- CashPayment only implements BasicPayment
- Interfaces are focused on specific capabilities
- No unnecessary exceptions
- Clear separation between basic and advanced features

### Explanation

The BAD example creates a monolithic PaymentMethod interface with 10 methods mixing basic and advanced features. CashPayment must implement 7 unsupported methods. The GOOD example segregates capabilities into focused interfaces (BasicPayment, AuthorizablePayment, TrackablePayment, etc.), allowing each payment type to choose relevant features.

---

## Example 6: Worker Interface

### BAD Example: Universal Worker Interface

```python
class Worker:
    def work(self):
        pass

    def take_break(self):
        pass

    def report_hours(self):
        pass

    def submit_expenses(self):
        pass

    def request_time_off(self):
        pass

    def attend_meeting(self):
        pass

    def manage_team(self):
        pass

    def approve_expenses(self):
        pass

    def hire_employee(self):
        pass

    def fire_employee(self):
        pass


class Intern(Worker):
    def work(self):
        print("Intern working")

    def take_break(self):
        print("Intern on break")

    def report_hours(self):
        print("Intern reporting hours")

    def submit_expenses(self):
        raise NotImplementedError("Interns don't submit expenses")

    def request_time_off(self):
        raise NotImplementedError("Not supported")

    def attend_meeting(self):
        print("Intern in meeting")

    def manage_team(self):
        raise NotImplementedError("Interns don't manage")

    def approve_expenses(self):
        raise NotImplementedError("Interns don't approve")

    def hire_employee(self):
        raise NotImplementedError("Interns don't hire")

    def fire_employee(self):
        raise NotImplementedError("Interns don't fire")


class Manager(Worker):
    def work(self):
        print("Manager working")

    def take_break(self):
        print("Manager on break")

    def report_hours(self):
        print("Manager reporting hours")

    def submit_expenses(self):
        print("Manager submitting expenses")

    def request_time_off(self):
        print("Manager requesting time off")

    def attend_meeting(self):
        print("Manager in meeting")

    def manage_team(self):
        print("Manager managing team")

    def approve_expenses(self):
        print("Manager approving expenses")

    def hire_employee(self):
        print("Manager hiring employee")

    def fire_employee(self):
        print("Manager firing employee")
```

**Problems:**
- Intern forced to implement 5 unsupported methods
- Interface mixes basic and management functions
- Not clear what role supports what capabilities
- High coupling between unrelated responsibilities

### GOOD Example: Role-Based Worker Interfaces

```python
from abc import ABC, abstractmethod


class BasicWorker(ABC):
    @abstractmethod
    def work(self):
        pass

    @abstractmethod
    def take_break(self):
        pass

    @abstractmethod
    def report_hours(self):
        pass


class ExpenseHandler(ABC):
    @abstractmethod
    def submit_expenses(self):
        pass


class TimeOffHandler(ABC):
    @abstractmethod
    def request_time_off(self):
        pass


class MeetingAttendee(ABC):
    @abstractmethod
    def attend_meeting(self):
        pass


class TeamManager(ABC):
    @abstractmethod
    def manage_team(self):
        pass


class ExpenseApprover(ABC):
    @abstractmethod
    def approve_expenses(self):
        pass


class HiringAuthority(ABC):
    @abstractmethod
    def hire_employee(self):
        pass

    @abstractmethod
    def fire_employee(self):
        pass


class Intern(BasicWorker, MeetingAttendee):
    def work(self):
        print("Intern working")

    def take_break(self):
        print("Intern on break")

    def report_hours(self):
        print("Intern reporting hours")

    def attend_meeting(self):
        print("Intern in meeting")


class RegularEmployee(BasicWorker, ExpenseHandler, TimeOffHandler, MeetingAttendee):
    def work(self):
        print("Employee working")

    def take_break(self):
        print("Employee on break")

    def report_hours(self):
        print("Employee reporting hours")

    def submit_expenses(self):
        print("Employee submitting expenses")

    def request_time_off(self):
        print("Employee requesting time off")

    def attend_meeting(self):
        print("Employee in meeting")


class Manager(BasicWorker, ExpenseHandler, TimeOffHandler, MeetingAttendee, TeamManager, ExpenseApprover, HiringAuthority):
    def work(self):
        print("Manager working")

    def take_break(self):
        print("Manager on break")

    def report_hours(self):
        print("Manager reporting hours")

    def submit_expenses(self):
        print("Manager submitting expenses")

    def request_time_off(self):
        print("Manager requesting time off")

    def attend_meeting(self):
        print("Manager in meeting")

    def manage_team(self):
        print("Manager managing team")

    def approve_expenses(self):
        print("Manager approving expenses")

    def hire_employee(self):
        print("Manager hiring employee")

    def fire_employee(self):
        print("Manager firing employee")
```

**Improvements:**
- Intern only implements relevant interfaces
- Interfaces represent specific capabilities
- Clear separation between basic and advanced roles
- Easy to compose roles as needed

### Explanation

The BAD example creates a monolithic Worker interface with 10 methods mixing basic work and management functions. Intern must implement 5 unsupported management methods. The GOOD example segregates capabilities into role-based interfaces (BasicWorker, ExpenseHandler, TeamManager, etc.), allowing each role to implement only relevant capabilities.

---

## Example 7: Multimedia Player

### BAD Example: All Media Types Interface

```python
class MediaPlayer:
    def play_audio(self, file):
        pass

    def pause_audio(self):
        pass

    def stop_audio(self):
        pass

    def seek_audio(self, position):
        pass

    def get_audio_position(self):
        pass

    def play_video(self, file):
        pass

    def pause_video(self):
        pass

    def stop_video(self):
        pass

    def seek_video(self, position):
        pass

    def get_video_position(self):
        pass

    def get_video_dimensions(self):
        pass

    def display_subtitles(self, enabled):
        pass

    def take_screenshot(self):
        pass

    def display_image(self, file):
        pass

    def rotate_image(self, angle):
        pass

    def zoom_image(self, level):
        pass


class AudioPlayer(MediaPlayer):
    def play_audio(self, file):
        print(f"Playing audio: {file}")

    def pause_audio(self):
        print("Audio paused")

    def stop_audio(self):
        print("Audio stopped")

    def seek_audio(self, position):
        print(f"Seeking audio to: {position}")

    def get_audio_position(self):
        return "00:00:00"

    def play_video(self, file):
        raise NotImplementedError("No video support")

    def pause_video(self):
        raise NotImplementedError("No video support")

    def stop_video(self):
        raise NotImplementedError("No video support")

    def seek_video(self, position):
        raise NotImplementedError("No video support")

    def get_video_position(self):
        raise NotImplementedError("No video support")

    def get_video_dimensions(self):
        raise NotImplementedError("No video support")

    def display_subtitles(self, enabled):
        raise NotImplementedError("No video support")

    def take_screenshot(self):
        raise NotImplementedError("No video support")

    def display_image(self, file):
        raise NotImplementedError("No image support")

    def rotate_image(self, angle):
        raise NotImplementedError("No image support")

    def zoom_image(self, level):
        raise NotImplementedError("No image support")
```

**Problems:**
- AudioPlayer must implement 9 unsupported methods
- Interface mixes audio, video, and image operations
- Unnecessary complexity for single-media players
- Not clear what player supports what media types

### GOOD Example: Segregated Media Interfaces

```python
from abc import ABC, abstractmethod


class AudioPlayable(ABC):
    @abstractmethod
    def play_audio(self, file):
        pass

    @abstractmethod
    def pause_audio(self):
        pass

    @abstractmethod
    def stop_audio(self):
        pass

    @abstractmethod
    def seek_audio(self, position):
        pass

    @abstractmethod
    def get_audio_position(self):
        pass


class VideoPlayable(ABC):
    @abstractmethod
    def play_video(self, file):
        pass

    @abstractmethod
    def pause_video(self):
        pass

    @abstractmethod
    def stop_video(self):
        pass

    @abstractmethod
    def seek_video(self, position):
        pass

    @abstractmethod
    def get_video_position(self):
        pass


class SubtitleControl(ABC):
    @abstractmethod
    def display_subtitles(self, enabled):
        pass


class ScreenshotCapture(ABC):
    @abstractmethod
    def take_screenshot(self):
        pass


class ImageDisplay(ABC):
    @abstractmethod
    def display_image(self, file):
        pass

    @abstractmethod
    def rotate_image(self, angle):
        pass

    @abstractmethod
    def zoom_image(self, level):
        pass


class AudioPlayer(AudioPlayable):
    def play_audio(self, file):
        print(f"Playing audio: {file}")

    def pause_audio(self):
        print("Audio paused")

    def stop_audio(self):
        print("Audio stopped")

    def seek_audio(self, position):
        print(f"Seeking audio to: {position}")

    def get_audio_position(self):
        return "00:00:00"


class VideoPlayer(VideoPlayable, SubtitleControl, ScreenshotCapture):
    def play_video(self, file):
        print(f"Playing video: {file}")

    def pause_video(self):
        print("Video paused")

    def stop_video(self):
        print("Video stopped")

    def seek_video(self, position):
        print(f"Seeking video to: {position}")

    def get_video_position(self):
        return "00:00:00"

    def display_subtitles(self, enabled):
        print(f"Subtitles: {enabled}")

    def take_screenshot(self):
        print("Screenshot taken")


class MediaPlayer(AudioPlayable, VideoPlayable, SubtitleControl, ScreenshotCapture, ImageDisplay):
    def play_audio(self, file):
        print(f"Playing audio: {file}")

    def pause_audio(self):
        print("Audio paused")

    def stop_audio(self):
        print("Audio stopped")

    def seek_audio(self, position):
        print(f"Seeking audio to: {position}")

    def get_audio_position(self):
        return "00:00:00"

    def play_video(self, file):
        print(f"Playing video: {file}")

    def pause_video(self):
        print("Video paused")

    def stop_video(self):
        print("Video stopped")

    def seek_video(self, position):
        print(f"Seeking video to: {position}")

    def get_video_position(self):
        return "00:00:00"

    def display_subtitles(self, enabled):
        print(f"Subtitles: {enabled}")

    def take_screenshot(self):
        print("Screenshot taken")

    def display_image(self, file):
        print(f"Displaying image: {file}")

    def rotate_image(self, angle):
        print(f"Rotating image: {angle}")

    def zoom_image(self, level):
        print(f"Zooming image: {level}")
```

**Improvements:**
- AudioPlayer only implements AudioPlayable
- Interfaces are focused on specific media types
- No unnecessary exceptions
- Clear separation of media capabilities

### Explanation

The BAD example creates a monolithic MediaPlayer interface with 15 methods mixing audio, video, and image operations. AudioPlayer must implement 9 unsupported methods. The GOOD example segregates media types into focused interfaces (AudioPlayable, VideoPlayable, ImageDisplay), allowing each player to choose its supported media types.

---

## Language-Specific Notes

### Idioms and Patterns

- **ABC module**: Use `abc.ABC` and `@abstractmethod` to define interfaces
- **Multiple inheritance**: Python allows multiple interface implementation
- **Protocol classes**: Use `typing.Protocol` for structural subtyping
- **Composition over inheritance**: Prefer composition to avoid fat interfaces
- **Duck typing**: Can use implicit interfaces but explicit ABCs improve clarity

### Language Features

**Features that help:**
- **ABC module**: Formal way to define interfaces
- **Multiple inheritance**: Implement multiple focused interfaces
- **Type hints**: Document expected interface members
- **Protocol**: Structural subtyping for flexibility
- **Abstract properties**: Define required attributes in interfaces

**Features that hinder:**
- **Duck typing**: Can mask interface issues until runtime
- **No formal interfaces**: Rely on conventions and ABCs
- **Optional typing**: Type hints not enforced at runtime
- **Dynamic class modification**: Can break interface contracts at runtime

### Framework Considerations

- **Django**: Fat model interfaces common, consider custom managers
- **Pyramid/Flask**: Use dependency injection with focused interfaces
- **FastAPI**: Dependency injection supports interface segregation
- **pytest**: Mock interfaces for testing

### Common Pitfalls

1. **Fat interfaces**: Keep interfaces focused on single responsibility
2. **NotImplementedError**: Indicates interface should be split
3. **God classes**: Often have too many implemented interfaces
4. **Mixed concerns**: Separate unrelated functionality into different interfaces
5. **Over-segregation**: Don't create too many tiny interfaces without purpose
