import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../features/auth/auth_controller.dart';
import '../features/translation/language_selector.dart';
import '../features/translation/translation_text.dart';
import '../shared/state_views.dart';
import '../shared/validators.dart';
import 'register_screen.dart';

/// Which login portal the user picked on this screen — display-only. It
/// never gates or changes the actual login call: both portals submit to
/// the exact same `AuthController.login(username, password)`, which hits
/// the same `/api/v1/auth/login` endpoint and trusts only the role the
/// backend actually returns (see AuthGate, which routes on
/// `session.role`, not on this selection). Picking the wrong portal for
/// your account still logs in correctly — this only changes labels.
enum LoginPortal { homeUser, collector }

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _submitting = false;
  LoginPortal _portal = LoginPortal.homeUser;

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _submitting = true);
    await context.read<AuthController>().login(_usernameController.text.trim(), _passwordController.text);
    if (mounted) setState(() => _submitting = false);
  }

  bool get _isCollectorPortal => _portal == LoginPortal.collector;

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    return Scaffold(
      appBar: AppBar(title: Text(context.tr('Kabadiwala Connect'))),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Before login, so users can pick their language before
                // entering credentials; the choice applies app-wide.
                const Card(child: LanguageSettingTile()),
                const SizedBox(height: 16),
                Icon(Icons.recycling, size: 64, color: Theme.of(context).colorScheme.primary),
                const SizedBox(height: 16),
                SegmentedButton<LoginPortal>(
                  key: const Key('login_portal_selector'),
                  segments: [
                    ButtonSegment(
                      value: LoginPortal.homeUser,
                      label: Text(context.tr('Home User')),
                      icon: Icon(Icons.home_outlined),
                    ),
                    ButtonSegment(
                      value: LoginPortal.collector,
                      label: Text(context.tr('Collector')),
                      icon: Icon(Icons.local_shipping_outlined),
                    ),
                  ],
                  selected: {_portal},
                  onSelectionChanged: _submitting
                      ? null
                      : (selection) => setState(() => _portal = selection.first),
                ),
                const SizedBox(height: 16),
                Text(
                  _isCollectorPortal ? context.tr('Collector Login') : context.tr('Home User Login'),
                  key: const Key('login_heading'),
                  style: Theme.of(context).textTheme.headlineSmall,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                if (auth.errorMessage != null) InlineErrorBanner(message: auth.errorMessage!),
                TextFormField(
                  key: const Key('login_username_field'),
                  controller: _usernameController,
                  decoration: InputDecoration(labelText: _isCollectorPortal ? context.tr('Employee ID') : context.tr('Username')),
                  validator: (v) => context.trOrNull(Validators.username(v)),
                  textInputAction: TextInputAction.next,
                ),
                const SizedBox(height: 16),
                TextFormField(
                  key: const Key('login_password_field'),
                  controller: _passwordController,
                  decoration: InputDecoration(labelText: context.tr('Password')),
                  obscureText: true,
                  validator: (v) => context.trOrNull(Validators.password(v)),
                  onFieldSubmitted: (_) => _submit(),
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  key: const Key('login_submit_button'),
                  onPressed: _submitting ? null : _submit,
                  child: _submitting
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Text(context.tr('Log In')),
                ),
                const SizedBox(height: 12),
                // Collectors have no self-registration path anywhere in
                // this app or the backend — account creation is
                // admin-only (Section 5 of the architecture doc) — so
                // this link only makes sense for the Home User portal.
                if (!_isCollectorPortal)
                  TextButton(
                    onPressed: _submitting
                        ? null
                        : () => Navigator.of(context).push(
                              MaterialPageRoute(builder: (_) => const RegisterScreen()),
                            ),
                    child: Text(context.tr("Don't have an account? Register")),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
