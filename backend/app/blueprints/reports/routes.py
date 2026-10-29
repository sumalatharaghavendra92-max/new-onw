from flask import Blueprint, make_response
from app.utils.rbac import role_required
from app.models import Trip, TripStatus
from app.services.trip_workflow import selected, iso, serialize
from app.services.analytics import summary
import io
import pandas as pd
from reportlab.pdfgen import canvas

reports_bp = Blueprint('reports', __name__)


def safe_cell(value):
    # Avoid spreadsheet formula execution in user-controlled place names.
    return "'" + value if isinstance(value, str) and value.startswith(('=', '+', '-', '@')) else value


@reports_bp.route('/export/excel')
@role_required('admin')
def export_excel():
    columns = ['Trip ID', 'Source', 'Destination', 'Vehicle', 'Selected route km',
               'Predicted CO2 kg', 'Estimated avoided CO2 kg', 'Reported fuel L (unverified)',
               'Reported CO2 kg (unverified)', 'Prediction mode', 'Completed at UTC']
    rows = []
    for trip in Trip.query.filter_by(status=TripStatus.completed).order_by(Trip.id.desc()).all():
        route = selected(trip)
        rows.append([trip.id, safe_cell(trip.source), safe_cell(trip.destination), safe_cell(trip.vehicle.vehicle_no),
                     route['distanceKm'] if route else None, route['co2Kg'] if route else None,
                     serialize(trip)['estimatedSavingsKg'],
                     trip.actual_fuel_l, trip.actual_co2_kg,
                     trip.plan.prediction_mode if trip.plan else 'Legacy record; unavailable', iso(trip.end_time)])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(rows, columns=columns).to_excel(writer, index=False, sheet_name='Completed trips')
        pd.DataFrame({'Notes': ['Avoided CO2 is a modeled signed difference versus the fastest alternative.',
                               'Blank measurements mean not recorded, not zero. Reports are driver-entered and unverified.',
                               'Evidence-withheld trips are excluded from avoided CO2 estimates.',
                               'Model estimates assume medium traffic and clear weather; not verified savings.']}).to_excel(writer, index=False, sheet_name='Methodology')
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = 'attachment; filename=gogreen_fleet_report.xlsx'
    return response


@reports_bp.route('/export/pdf')
@role_required('admin')
def export_pdf():
    stats = summary()
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.setTitle('GoGreen fleet impact report')
    pdf.setFillColorRGB(.06, .24, .19)
    pdf.rect(0, 700, 600, 142, fill=1, stroke=0)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont('Helvetica-Bold', 25)
    pdf.drawString(45, 780, 'GoGreen | Fleet impact')
    pdf.setFont('Helvetica', 11)
    pdf.drawString(45, 750, 'Saved journeys. Transparent estimates.')
    pdf.setFillColorRGB(.1, .2, .16)
    pdf.setFont('Helvetica', 12)
    lines = [f"Generated: {stats['updated_at']}",
             f"Completed journeys: {stats['total_trips']}",
             f"Trips with comparable route predictions: {stats['comparable_trips']}",
             f"Selected-route distance: {stats['distance_km']} km",
             f"Selected-route predicted CO2: {stats['predicted_co2_kg']} kg",
             f"Estimated avoided CO2: {stats['co2_saved_kg']} kg",
             '', 'Methodology',
             'Avoided CO2 is the signed predicted difference from the fastest route.',
             'Only completed trips with saved selections contribute to these estimates.',
             'Model inputs assume medium traffic and clear weather.',
             'Predictions are not measurements or verified emissions reductions.',
             'Download the Excel report for trip details and recorded measurements.']
    for i, line in enumerate(lines):
        pdf.drawString(45, 665 - i * 27, line)
    pdf.save()
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=gogreen_impact.pdf'
    return response
