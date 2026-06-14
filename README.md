# Sunrise Worker Handler (SR-Worker-Handler)

A comprehensive worker shift management and scheduling system for supermarkets, designed to streamline workforce organization, task assignment, and operational tracking.

## Features

### Core Features

#### 1. **Worker Registry Management**
- Add and manage workers with detailed profiles
- Store worker information including name, role, and bio
- Support for multiple roles: Owner, Manager, and Worker
- View all registered workers in an organized table interface

#### 2. **Role-Based Task Assignment**
- Predefined task lists for each role:
  - **Owner**: 25+ tasks including strategic planning, financial review, supplier meetings, and business relations
  - **Manager**: Inventory checks, staff scheduling, store inspection, and customer relations
  - **Worker**: Operational tasks including stocking, cashier duties, cleaning, and product handling
- Dynamic task list loading based on worker role
- Task customization per shift assignment

#### 3. **Shift Planning & Scheduling**
- Create and manage shifts with specific dates and time slots
- Assign workers to shifts with start and end times
- Support for multiple shifts per day across different workers
- Shift editing with worker and time modification capabilities
- Shift deletion with confirmation prompts
- Weekly shift planner view for comprehensive scheduling overview

#### 4. **Voluntary Shift Management**
- Allow workers to take on additional voluntary shifts
- Date and time selection for voluntary assignments
- Custom task selection for voluntary work
- Visual distinction between scheduled and voluntary shifts

#### 5. **Late Entry & Attendance Tracking**
- Track late arrivals with specific entry times
- Set late entry times separate from scheduled start times
- Late arrival visualization on occupancy charts (shown in red overlay)
- Complete attendance recording and modifications

#### 6. **Timesheet & Hour Tracking**
- Track actual hours worked per shift
- Timesheet data storage and retrieval
- Progress bar visualization showing completion status
- Hour calculations with late entry considerations
- Worker productivity metrics

#### 7. **Visual Occupancy Charts**
- Hourly occupancy visualization for daily shifts
- Color-coded worker roles:
  - Light Blue: Owner
  - Light Orange: Manager
  - Light Green: Worker
  - Greenish Grey: Voluntary Shifts
- Red overlay indicators for late entries
- Interactive chart with click functionality for shift details
- Supports both scheduled and actual hours display
- Customizable hour ranges (start and end times)

#### 8. **Shift Export & Reporting**
- Export shift data to PDF format with detailed shift information
- Generate PNG snapshots of shift schedules and occupancy charts
- Comprehensive shift reports with worker assignments and tasks
- Time-based export naming for organized document management

#### 9. **Week-Based Calendar Navigation**
- Week selection dialog for easy date navigation
- Calendar widget for intuitive date picking
- Week view switching for organized schedule management

#### 10. **Database Persistence**
- SQLite database for reliable data storage
- Automatic database initialization on first run
- Schema includes:
  - Workers table: name, role, bio
  - Shifts table: date, worker assignments, times, tasks, timesheet data
  - Support for metadata fields (full_date, is_voluntary)
- Graceful column addition for backwards compatibility

### Backend Features

#### 11. **RESTful API Server**
- Flask-based REST API running on `http://127.0.0.1:5000`
- Endpoints:
  - `GET/POST /api/workers` - Manage worker database
  - `GET /api/tasks/<role>` - Retrieve role-specific tasks
  - `GET/POST /api/shifts` - Handle shift operations
  - Additional endpoints for shift editing and deletion
- Automatic API server startup with the application
- Error logging and request timeout handling (3-second default)

#### 12. **Multi-threaded Architecture**
- Background daemon thread for API server
- Non-blocking UI operations
- Responsive interface during API calls
- Graceful server shutdown on application exit

### UI/UX Features

#### 13. **PyQt6 Desktop Interface**
- Modern, responsive GUI built with PyQt6
- Custom flow layout for flexible widget arrangement
- Multiple dialog windows for specialized operations:
  - Calendar selection dialog
  - Late entry time picker
  - Voluntary shift creation dialog
  - Shift editing dialog
- Tabbed interface for multi-section navigation

#### 14. **Interactive Elements**
- Click-to-edit shift functionality on occupancy charts
- Context menus for shift operations
- Form validations and error messages
- Status indicators and confirmations

#### 15. **Data Validation & Error Handling**
- API timeout handling with error messages
- Request exception logging
- Worker availability checking
- Task assignment validation
- Duplicate entry prevention

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: PyQt6 (Python)
- **Database**: SQLite3
- **HTTP Communication**: Requests library
- **Export**: PyQt6 PDF/PNG rendering
- **Threading**: Python threading module

## Project Structure

```
sr-worker-handler/
├── main.py                 # PyQt6 desktop application
├── api.py                  # Flask REST API backend
├── supermarket.db          # SQLite database
└── exports/                # Shift schedule exports (PDF/PNG)
```

## Installation & Running

1. **Install Dependencies**:
   ```bash
   pip install PyQt6 Flask requests
   ```

2. **Run the Application**:
   ```bash
   python main.py
   ```
   - The application automatically starts the API server
   - The desktop interface launches with full shift management capabilities

3. **Access API**:
   - Base URL: `http://127.0.0.1:5000/api`
   - Available during application runtime

## Key Use Cases

- **Daily Shift Management**: Create and modify daily work schedules
- **Worker Assignment**: Assign specific workers with role-based tasks
- **Attendance Tracking**: Record actual arrival times and work hours
- **Occupancy Planning**: Visualize coverage throughout operational hours
- **Report Generation**: Export shift schedules for records and analysis
- **Voluntary Work**: Manage additional work assignments beyond regular schedules

## Future Development Areas

- Additional export formats (Excel, CSV)
- Advanced reporting and analytics
- Worker performance metrics
- Notification system for shift changes
- Mobile companion app
- Multi-location support

---

**Last Updated**: June 14, 2026
