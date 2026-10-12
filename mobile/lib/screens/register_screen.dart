import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exception.dart';
import '../core/location_service.dart';
import '../features/auth/auth_controller.dart';
import '../features/home_user/home_user_repository.dart';
import '../features/home_user/models/ward.dart';
import '../features/translation/translation_text.dart';
import '../shared/state_views.dart';
import '../shared/validators.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _fullNameController = TextEditingController();
  final _addressController = TextEditingController();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _upiController = TextEditingController();
  final _locationService = LocationService();

  bool _loadingWards = true;
  String? _wardsError;
  List<Ward> _wards = [];
  String? _selectedWardId;

  bool _locating = false;
  bool _resolvingLocation = false;
  String? _locationError;
  String? _locationName;
  double? _lat;
  double? _lng;

  bool _submitting = false;
  String? _submitError;

  @override
  void initState() {
    super.initState();
    _loadWards();
  }

  @override
  void dispose() {
    _fullNameController.dispose();
    _addressController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    _upiController.dispose();
    super.dispose();
  }

  Future<void> _loadWards() async {
    setState(() {
      _loadingWards = true;
      _wardsError = null;
    });
    try {
      final wards = await context.read<HomeUserRepository>().listWards();
      if (!mounted) return;
      setState(() {
        _wards = wards;
        _loadingWards = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _wardsError = e.message;
        _loadingWards = false;
      });
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

  Future<void> _submit() async {
    setState(() => _submitError = null);
    if (!_formKey.currentState!.validate()) return;
    if (_selectedWardId == null) {
      setState(() => _submitError = 'Please select your ward.');
      return;
    }
    if (_lat == null || _lng == null) {
      setState(() => _submitError = 'Please capture your household location.');
      return;
    }

    setState(() => _submitting = true);
    try {
      final username = _usernameController.text.trim();
      final password = _passwordController.text;

      await context.read<HomeUserRepository>().register(
            username: username,
            password: password,
            fullName: _fullNameController.text.trim(),
            address: _addressController.text.trim(),
            wardId: _selectedWardId!,
            householdLat: _lat!,
            householdLng: _lng!,
            upiId: _upiController.text.trim().isEmpty ? null : _upiController.text.trim(),
          );

      if (!mounted) return;
      final auth = context.read<AuthController>();
      final loggedIn = await auth.login(username, password);
      if (!mounted) return;
      if (loggedIn) {
        Navigator.of(context).pop();
      } else {
        setState(() => _submitError = 'Registered successfully, but automatic login failed. Please log in manually.');
      }
    } on ApiException catch (e) {
      setState(() => _submitError = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(context.tr('Register — Home User'))),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (_submitError != null) InlineErrorBanner(message: _submitError!),
                TextFormField(
                  controller: _fullNameController,
                  decoration: InputDecoration(labelText: context.tr('Full name')),
                  validator: (v) => context.trOrNull(Validators.fullName(v)),
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _addressController,
                  decoration: InputDecoration(labelText: context.tr('Address')),
                  validator: (v) => context.trOrNull(Validators.address(v)),
                  maxLines: 2,
                ),
                const SizedBox(height: 16),
                _buildWardField(),
                const SizedBox(height: 16),
                _buildLocationField(),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _upiController,
                  decoration: InputDecoration(labelText: context.tr('UPI ID (optional)')),
                ),
                const Divider(height: 32),
                TextFormField(
                  controller: _usernameController,
                  decoration: InputDecoration(labelText: context.tr('Choose a username')),
                  validator: (v) => context.trOrNull(Validators.username(v)),
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _passwordController,
                  decoration: InputDecoration(labelText: context.tr('Choose a password')),
                  obscureText: true,
                  validator: (v) => context.trOrNull(Validators.password(v)),
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  key: const Key('register_submit_button'),
                  onPressed: _submitting ? null : _submit,
                  child: _submitting
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Text(context.tr('Register')),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildWardField() {
    if (_loadingWards) {
      return Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: LoadingView(message: context.tr('Loading wards…')));
    }
    if (_wardsError != null) {
      return ErrorView(message: _wardsError!, onRetry: _loadWards);
    }
    if (_wards.isEmpty) {
      return EmptyView(message: context.tr('No wards are configured yet. Ask an admin to add one before registering.'));
    }
    return DropdownButtonFormField<String>(
      key: const Key('register_ward_dropdown'),
      initialValue: _selectedWardId,
      decoration: InputDecoration(labelText: context.tr('Ward')),
      items: _wards
          .map((w) => DropdownMenuItem(value: w.wardId, child: Text('${w.name} (${w.wardId})')))
          .toList(),
      onChanged: (value) => setState(() => _selectedWardId = value),
      validator: (v) => context.trOrNull(Validators.ward(v)),
    );
  }

  Widget _buildLocationField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(context.tr('Household location'), style: Theme.of(context).textTheme.labelLarge),
        const SizedBox(height: 8),
        if (_lat != null && _lng != null)
          Text(
            _locationName == null
                ? '${context.tr('Captured:')} ${_lat!.toStringAsFixed(5)}, ${_lng!.toStringAsFixed(5)}'
                : '${context.tr('Captured:')} $_locationName',
          )
        else
          Text(context.tr('Not captured yet'), style: const TextStyle(color: Colors.grey)),
        if (_locationError != null) ...[
          const SizedBox(height: 4),
          Text(context.tr(_locationError!), style: const TextStyle(color: Colors.red)),
        ],
        const SizedBox(height: 8),
        OutlinedButton.icon(
          onPressed: _locating ? null : _captureLocation,
          icon: _locating
              ? const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.my_location),
          label: Text(
            _resolvingLocation ? context.tr('Finding city name...') : context.tr('Use current location'),
          ),
        ),
      ],
    );
  }
}
