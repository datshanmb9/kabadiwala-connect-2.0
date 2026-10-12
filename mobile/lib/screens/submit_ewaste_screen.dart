import 'dart:typed_data';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../core/api_exception.dart';
import '../core/idempotency_key_generator.dart';
import '../core/location_service.dart';
import '../core/photo_picker_service.dart';
import '../features/auth/auth_controller.dart';
import '../features/auth/models/auth_session.dart';
import '../features/ewaste/ewaste_repository.dart';
import '../features/ewaste/models/submission.dart';
import '../features/ewaste/offline/offline_submission_sync.dart';
import '../features/ewaste/widgets/photo_detection_widgets.dart';
import '../features/pricing/widgets/price_trend_card.dart';
import '../features/translation/translation_text.dart';
import '../shared/state_views.dart';
import '../shared/submission_status.dart';

class SubmitEwasteScreen extends StatefulWidget {
  final String wardId;
  const SubmitEwasteScreen({super.key, required this.wardId});

  @override
  State<SubmitEwasteScreen> createState() => _SubmitEwasteScreenState();
}

class _SubmitEwasteScreenState extends State<SubmitEwasteScreen> {
  final _photoPicker = PhotoPickerService();
  final _locationService = LocationService();
  final _categoryController = TextEditingController();
  final _weightController = TextEditingController();
  String? _selectedCondition;
  bool _safetyAcknowledged = false;

  // Generated once per submission attempt and reused across retries of
  // that SAME attempt, so a slow-network double-tap on Submit can't create
  // two separate submissions server-side.
  late final String _idempotencyKey;

  XFile? _photo;
  Uint8List? _photoBytes;
  bool _pickingPhoto = false;
  String? _photoError;
  PhotoClassificationResult? _photoClassification;
  PriceEstimate? _priceEstimate;
  bool _estimatingPrice = false;
  String? _priceError;

  bool _locating = false;
  bool _resolvingLocation = false;
  String? _locationError;
  String? _locationName;
  double? _lat;
  double? _lng;

  bool _submitting = false;
  String? _submitError;
  SubmissionCreateResult? _result;
  bool _savedOffline = false;

  @override
  void initState() {
    super.initState();
    _idempotencyKey = IdempotencyKeyGenerator.generate();
  }

  @override
  void dispose() {
    _categoryController.dispose();
    _weightController.dispose();
    super.dispose();
  }

  Future<void> _pickPhoto(ImageSource source) async {
    setState(() {
      _pickingPhoto = true;
      _photoError = null;
    });
    try {
      final file = await _photoPicker.pickPhoto(source: source);
      if (file == null) {
        if (mounted) setState(() => _pickingPhoto = false);
        return;
      }
      final bytes = await file.readAsBytes();
      if (!mounted) return;
      setState(() {
        _photo = file;
        _photoBytes = bytes;
      });

      final token = context.read<AuthController>().session?.accessToken;
      if (token == null) {
        throw const ApiException(
          errorCode: 'INVALID_TOKEN',
          message: 'Your session has expired. Please log in again.',
        );
      }
      final repository = context.read<EwasteRepository>();
      final photoFileId = await repository.uploadPhoto(
        accessToken: token,
        file: file,
      );
      final classification = await repository.classifyPhoto(
        accessToken: token,
        photoFileId: photoFileId,
      );
      if (!mounted) return;
      setState(() {
        _photoClassification = classification;
        // Material/category is free text end to end (submission, lot,
        // pricing input), so the actual detected item is used rather than
        // the classifier's generic bucket ('e-waste-small-appliances').
        if (classification.category != null) {
          _categoryController.text =
              classification.detectedItemName ?? classification.category!;
        }
        _safetyAcknowledged = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _photoError = '${context.tr('Image prediction failed:')} ${context.tr(e.message)}');
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _photoError = 'Could not access the camera/gallery.';
        _pickingPhoto = false;
      });
    } finally {
      if (mounted) setState(() => _pickingPhoto = false);
    }
  }

  Future<void> _captureLocation() async {
    setState(() {
      _locating = true;
      _resolvingLocation = false;
      _locationError = null;
    });
    try {
      final position = await _locationService.getCurrentLocation();
      if (!mounted) return;
      setState(() {
        _lat = position.latitude;
        _lng = position.longitude;
        _locationName = null;
        _resolvingLocation = true;
      });
      final locationName = await _locationService.getReadableLocation(position);
      if (!mounted) return;
      setState(() {
        _locationName = locationName;
        _resolvingLocation = false;
        if (locationName == null) {
          _locationError = 'Could not find a city name. Showing coordinates instead.';
        }
      });
    } on LocationException catch (e) {
      if (!mounted) return;
      setState(() => _locationError = e.message);
    } finally {
      if (mounted) {
        setState(() {
          _locating = false;
          _resolvingLocation = false;
        });
      }
    }
  }

  Future<void> _reviewAndSubmit() async {
    if (_photo == null) {
      setState(() => _submitError = 'Please capture or select a photo first.');
      return;
    }
    if (_lat == null || _lng == null) {
      setState(() => _submitError = 'Please capture your location first.');
      return;
    }
    final category = _categoryController.text.trim();
    final weight = double.tryParse(_weightController.text.trim());
    if (_selectedCondition == null) {
      setState(() => _submitError = 'Please select the item condition.');
      return;
    }
    if (category.isEmpty) {
      setState(() => _submitError = 'Please enter a material or category.');
      return;
    }
    if (weight == null || weight <= 0) {
      setState(
        () => _submitError =
            'Please enter an approximate weight greater than zero.',
      );
      return;
    }
    if (_priceEstimate == null) {
      setState(() => _submitError = 'Please get a price estimate first.');
      return;
    }
    if (!_safetyAcknowledged) {
      setState(() => _submitError = 'Please review the safety measures first.');
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(context.tr('Review pickup request')),
        content: Text(
          '${context.tr('Category:')} $category\n'
          '${context.tr('Approximate weight:')} ${weight.toStringAsFixed(2)} kg\n'
          '${context.tr('Pickup location:')} ${_locationName ?? '${_lat!.toStringAsFixed(5)}, ${_lng!.toStringAsFixed(5)}'}',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(context.tr('Edit')),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(context.tr('Submit request')),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    await _submit(category: category, weight: weight);
  }

  Future<void> _submit({
    required String category,
    required double weight,
  }) async {
    setState(() {
      _submitting = true;
      _submitError = null;
    });
    final session = context.read<AuthController>().session;
    final token = session?.accessToken;
    if (token == null) {
      setState(() {
        _submitting = false;
        _submitError = 'Your session has expired. Please log in again.';
      });
      return;
    }

    String? photoFileId;
    try {
      final repository = context.read<EwasteRepository>();
      photoFileId = await repository.uploadPhoto(
        accessToken: token,
        file: _photo!,
      );
      final result = await repository.createSubmission(
        accessToken: token,
        wardId: widget.wardId,
        photoFileId: photoFileId,
        homeLat: _lat!,
        homeLng: _lng!,
        category: category,
        condition: _selectedCondition,
        approximateWeightKg: weight,
        priceEstimate: _priceEstimate,
        idempotencyKey: _idempotencyKey,
      );
      if (!mounted) return;
      setState(() {
        _result = result;
        _submitting = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      if (isNetworkFailure(e) && !kIsWeb && await _saveOffline(session!, category, weight, photoFileId)) {
        return;
      }
      if (!mounted) return;
      setState(() {
        _submitError = e.message;
        _submitting = false;
      });
    }
  }

  /// No connection: keep the complete submission (and a durable copy of the
  /// photo) on the device, to be sent automatically once back online. The
  /// SAME idempotency key is stored, so if this attempt actually reached the
  /// server before the connection dropped, the later sync returns that
  /// submission instead of creating another.
  Future<bool> _saveOffline(
    AuthSession session,
    String category,
    double weight,
    String? photoFileId,
  ) async {
    try {
      await context.read<OfflineSubmissionSync>().enqueue(
            userId: session.userId,
            idempotencyKey: _idempotencyKey,
            wardId: widget.wardId,
            homeLat: _lat!,
            homeLng: _lng!,
            category: category,
            condition: _selectedCondition,
            approximateWeightKg: weight,
            priceEstimate: _priceEstimate,
            photoBytes: _photoBytes ?? await _photo!.readAsBytes(),
            photoName: _photo!.name,
            photoMimeType: _photo!.mimeType,
            photoFileId: photoFileId,
          );
    } catch (_) {
      return false;
    }
    if (!mounted) return true;
    setState(() {
      _savedOffline = true;
      _submitting = false;
    });
    return true;
  }

  Future<void> _estimatePrice() async {
    final category = _categoryController.text.trim();
    final weight = double.tryParse(_weightController.text.trim());
    if (category.isEmpty) {
      setState(() => _priceError = 'Enter or confirm a material/category first.');
      return;
    }
    if (_selectedCondition == null) {
      setState(() => _priceError = 'Select the item condition first.');
      return;
    }
    if (weight == null || weight <= 0) {
      setState(() => _priceError = 'Enter an approximate weight greater than zero.');
      return;
    }
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) {
      setState(() => _priceError = 'Your session has expired. Please log in again.');
      return;
    }
    setState(() {
      _estimatingPrice = true;
      _priceError = null;
    });
    try {
      final estimate = await context.read<EwasteRepository>().estimatePrice(
        accessToken: token,
        productType: category,
        condition: _selectedCondition!,
        weightKg: weight,
        // The model requires a location, while the user flow captures GPS
        // after estimation. Ward is the server-assigned location fallback.
        location: _locationName ?? widget.wardId,
      );
      if (!mounted) return;
      setState(() => _priceEstimate = estimate);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _priceError = e.message);
    } finally {
      if (mounted) setState(() => _estimatingPrice = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_result != null) return _buildSuccessScreen(_result!);
    if (_savedOffline) return _buildSavedOfflineScreen();

    return Scaffold(
      appBar: AppBar(title: Text(context.tr('Submit E-Waste'))),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (_submitError != null)
                InlineErrorBanner(message: _submitError!),
              Text(context.tr('Photo'), style: Theme.of(context).textTheme.labelLarge),
              const SizedBox(height: 8),
              _buildPhotoPreview(),
              if (_photoClassification != null)
                PhotoDetectionResult(result: _photoClassification!),
              if (_photoError != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    context.tr(_photoError!),
                    style: const TextStyle(color: Colors.red),
                  ),
                ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      key: const Key('pick_photo_camera_button'),
                      onPressed: _pickingPhoto
                          ? null
                          : () => _pickPhoto(ImageSource.camera),
                      icon: const Icon(Icons.camera_alt_outlined),
                      label: Text(context.tr('Camera')),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      key: const Key('pick_photo_gallery_button'),
                      onPressed: _pickingPhoto
                          ? null
                          : () => _pickPhoto(ImageSource.gallery),
                      icon: const Icon(Icons.photo_library_outlined),
                      label: Text(context.tr('Gallery')),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                context.tr('The selected image is uploaded before the submission is sent. Category and weight remain available as manual fallback.'),
                style: Theme.of(context).textTheme.bodySmall
                    ?.copyWith(color: Colors.grey),
              ),
              const Divider(height: 32),
              Text(
                context.tr('Material and quantity'),
                style: Theme.of(context).textTheme.labelLarge,
              ),
              const SizedBox(height: 8),
              TextField(
                key: const Key('submission_category_field'),
                controller: _categoryController,
                textInputAction: TextInputAction.next,
                onChanged: (_) => setState(() {
                  _priceEstimate = null;
                  _priceError = null;
                  _safetyAcknowledged = false;
                }),
                decoration: InputDecoration(
                  labelText: context.tr('Material/category'),
                  hintText: context.tr('e.g. mobile phones, cables'),
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                key: const Key('submission_condition_dropdown'),
                initialValue: _selectedCondition,
                decoration: InputDecoration(
                  labelText: context.tr('Condition'),
                  border: OutlineInputBorder(),
                ),
                // Values stay English (they are what the backend stores);
                // only the displayed label is localized.
                items: [
                  for (final condition in const ['New', 'Like New', 'Good', 'Used', 'Damaged', 'Non-Working'])
                    DropdownMenuItem(value: condition, child: Text(context.tr(condition))),
                ],
                onChanged: (value) => setState(() {
                  _selectedCondition = value;
                  _priceEstimate = null;
                  _priceError = null;
                }),
                validator: (value) => value == null ? context.tr('Select a condition.') : null,
              ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('submission_weight_field'),
                controller: _weightController,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                onChanged: (_) => setState(() {
                  _priceEstimate = null;
                  _priceError = null;
                }),
                decoration: InputDecoration(
                  labelText: context.tr('Approximate weight (kg)'),
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                key: const Key('get_price_estimate_button'),
                onPressed: _estimatingPrice ? null : _estimatePrice,
                icon: _estimatingPrice
                    ? const SizedBox(
                        height: 16,
                        width: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.calculate_outlined),
                label: Text(context.tr('Get Price Estimate')),
              ),
              if (_priceError != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    context.tr(_priceError!),
                    style: const TextStyle(color: Colors.red),
                  ),
                ),
              if (_priceEstimate != null) _buildPriceEstimate(_priceEstimate!),
              if (_categoryController.text.trim().isNotEmpty)
                SafetyMeasuresCard(
                  itemName: _categoryController.text,
                  onContinue: () => setState(() {
                    _safetyAcknowledged = true;
                    _submitError = null;
                  }),
                ),
              if (_safetyAcknowledged) ...[
                const Divider(height: 32),
                Text(context.tr('Location'), style: Theme.of(context).textTheme.labelLarge),
              const SizedBox(height: 8),
              if (_lat != null && _lng != null)
                  Text(
                    _locationName == null
                        ? '${context.tr('Captured:')} ${_lat!.toStringAsFixed(5)}, ${_lng!.toStringAsFixed(5)}'
                        : '${context.tr('Captured:')} $_locationName',
                  )
              else
                  Text(
                    context.tr('Not captured yet'),
                  style: TextStyle(color: Colors.grey),
                ),
              if (_locationError != null) ...[
                const SizedBox(height: 4),
                Text(
                  context.tr(_locationError!),
                  style: const TextStyle(color: Colors.red),
                ),
              ],
              const SizedBox(height: 8),
              OutlinedButton.icon(
                key: const Key('capture_location_button'),
                onPressed: _locating ? null : _captureLocation,
                icon: _locating
                    ? const SizedBox(
                        height: 16,
                        width: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.my_location),
                label: Text(
                  _resolvingLocation
                      ? context.tr('Finding city name...')
                      : context.tr('Use current location'),
                ),
              ),
              ],
              const SizedBox(height: 32),
              ElevatedButton(
                key: const Key('submit_ewaste_confirm_button'),
                onPressed: _submitting ? null : _reviewAndSubmit,
                child: _submitting
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(context.tr('Submit')),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPhotoPreview() {
    if (_pickingPhoto) return const LoadingView();
    if (_photoBytes == null) {
      return Container(
        height: 160,
        decoration: BoxDecoration(
          border: Border.all(color: Colors.grey.shade300),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Center(
          child: Text(
            context.tr('No photo selected'),
            style: const TextStyle(color: Colors.grey),
          ),
        ),
      );
    }
    return ClipRRect(
      borderRadius: BorderRadius.circular(8),
      child: Image.memory(
        _photoBytes!,
        height: 160,
        fit: BoxFit.cover,
        width: double.infinity,
      ),
    );
  }

  Widget _buildPriceEstimate(PriceEstimate estimate) {
    return Card(
      key: const Key('price_estimate_card'),
      margin: const EdgeInsets.only(top: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(context.tr('Price Estimation'), style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text('${context.tr('Material:')} ${estimate.productType}'),
            Text('${context.tr('Condition:')} ${estimate.condition}'),
            Text('${context.tr('Weight:')} ${estimate.weightKg.toStringAsFixed(2)} kg'),
            const SizedBox(height: 8),
            Text(
              '${context.tr('Estimated price:')} ₹${estimate.minPrice.toStringAsFixed(2)} – '
              '₹${estimate.maxPrice.toStringAsFixed(2)} / kg',
            ),
            Text(
              '${context.tr('Estimated total:')} ${estimate.estimatedTotalLabel}',
            ),
            PriceTrendCard(item: estimate.productType, wardId: widget.wardId),
            const SizedBox(height: 8),
            Text(
              context.tr('Estimated value only. Final price may change after actual weight, condition verification, and recycler offer.'),
              style: TextStyle(color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSavedOfflineScreen() {
    return Scaffold(
      appBar: AppBar(title: Text(context.tr('Submit E-Waste'))),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off, color: Colors.orange, size: 72),
              const SizedBox(height: 16),
              Text(
                context.tr(offlineSavedMessage),
                key: const Key('offline_saved_message'),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                key: const Key('offline_saved_done_button'),
                onPressed: () => Navigator.of(context).pop(),
                child: Text(context.tr('Done')),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSuccessScreen(SubmissionCreateResult result) {
    final info = submissionStatusInfo(result.status, translate: context.tr);
    return Scaffold(
      appBar: AppBar(title: Text(context.tr('Submission Sent'))),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.check_circle, color: Colors.green, size: 72),
              const SizedBox(height: 16),
              Text(
                context.tr('Submitted successfully'),
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(
                '${context.tr('Submission ID:')} ${result.submissionId}',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Chip(
                label: Text(
                  info.label,
                  style: const TextStyle(color: Colors.white),
                ),
                backgroundColor: info.color,
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                key: const Key('submission_done_button'),
                onPressed: () => Navigator.of(context).pop(),
                child: Text(context.tr('Done')),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
