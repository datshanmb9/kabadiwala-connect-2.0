import 'package:flutter/material.dart';

/// Maps the exact backend status strings (see
/// backend/app/state_machines/ewaste_states.py) to a display label and
/// color. Deliberately generic over every state the backend's full state
/// machine allow-list defines — not just the Phase 2 subset a Home User
/// can currently observe — so a status string is never silently dropped;
/// unrecognized values still get a title-cased label instead of crashing.
class SubmissionStatusInfo {
  final String label;
  final Color color;

  const SubmissionStatusInfo(this.label, this.color);
}

SubmissionStatusInfo submissionStatusInfo(
  String status, {
  String Function(String source)? translate,
}) {
  String display(String value) => translate?.call(value) ?? value;

  switch (status) {
    case 'CREATED':
    case 'PHOTO_CAPTURED':
      return SubmissionStatusInfo(display(_titleCase(status)), Colors.grey);
    case 'WAITING_FOR_COLLECTION':
      return SubmissionStatusInfo(display('Waiting for Collection'), Colors.orange);
    case 'COLLECTOR_ASSIGNED':
    case 'COLLECTOR_ACCEPTED':
    case 'COLLECTING':
    case 'HANDOVER_PENDING':
      return SubmissionStatusInfo(display(_titleCase(status)), Colors.blue);
    case 'LOCATION_VERIFIED':
    case 'AT_RRR':
    case 'CLASSIFIED':
    case 'LOT_CREATED':
    case 'LISTED_FOR_BIDDING':
    case 'BID_SELECTED':
    case 'LOGISTICS_BOOKED':
    case 'READY_FOR_COLLECTION':
    case 'PAYMENT_PENDING':
      return SubmissionStatusInfo(display(_titleCase(status)), Colors.teal);
    case 'COLLECTED':
    case 'PAID':
    case 'COMPLETED':
      return SubmissionStatusInfo(display(_titleCase(status)), Colors.green);
    case 'FLAGGED_FOR_REVIEW':
    case 'REJECTED':
      return SubmissionStatusInfo(display(_titleCase(status)), Colors.red);
    default:
      return SubmissionStatusInfo(display(_titleCase(status)), Colors.grey);
  }
}

String _titleCase(String value) => value
    .split('_')
    .where((w) => w.isNotEmpty)
    .map((w) => '${w[0]}${w.substring(1).toLowerCase()}')
    .join(' ');
