import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/core/api_exception.dart';
import 'package:kabadiwala_mobile/features/rewards/rewards_repository.dart';

http.Response _json(Map<String, dynamic> body, int status) =>
    http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json'});

void main() {
  group('RewardsRepository.listMyRewards', () {
    test('parses the rewards list and attaches the bearer token', () async {
      String? capturedAuthHeader;
      final repo = RewardsRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            capturedAuthHeader = req.headers['Authorization'];
            return _json({
              'success': true,
              'rewards': [
                {
                  'reward_id': 'rwd-1',
                  'home_user_id': 'user-1',
                  'period': '2026-09',
                  'points': 10,
                  'amount': '5.00',
                  'status': 'CREDITED',
                  'created_at': '2026-09-01T00:00:00',
                },
              ],
            }, 200);
          }),
        ),
      );
      final rewards = await repo.listMyRewards('tok-1');
      expect(rewards, hasLength(1));
      expect(rewards.first.amount, '5.00');
      expect(capturedAuthHeader, 'Bearer tok-1');
    });
  });

  group('RewardsRepository.redeem', () {
    test('posts to the correct path with Idempotency-Key and no body', () async {
      late Map<String, String> capturedHeaders;
      String? capturedPath;
      final repo = RewardsRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            capturedPath = req.url.path;
            capturedHeaders = req.headers;
            return _json({
              'txn_id': 'txn-1',
              'home_user_id': 'user-1',
              'reward_id': 'rwd-1',
              'type': 'REDEMPTION',
              'amount': '5.00',
              'status': 'SUCCEEDED',
              'created_at': '2026-09-01T00:00:00',
            }, 200);
          }),
        ),
      );
      final txn = await repo.redeem(rewardId: 'rwd-1', accessToken: 'tok-1', idempotencyKey: 'idem-1');
      expect(capturedPath, '/api/v1/rewards/rwd-1/redeem');
      expect(capturedHeaders['Idempotency-Key'], 'idem-1');
      expect(txn.succeeded, isTrue);
    });

    test('a retry with the SAME idempotency key sends the same key value again', () async {
      final sentKeys = <String?>[];
      final repo = RewardsRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            sentKeys.add(req.headers['Idempotency-Key']);
            return _json({
              'txn_id': 'txn-1',
              'home_user_id': 'user-1',
              'reward_id': 'rwd-1',
              'type': 'REDEMPTION',
              'amount': '5.00',
              'status': 'SUCCEEDED',
              'created_at': '2026-09-01T00:00:00',
            }, 200);
          }),
        ),
      );
      const key = 'fixed-redeem-retry-key';
      await repo.redeem(rewardId: 'rwd-1', accessToken: 'tok-1', idempotencyKey: key);
      await repo.redeem(rewardId: 'rwd-1', accessToken: 'tok-1', idempotencyKey: key);
      expect(sentKeys, [key, key]);
    });

    test('propagates NO_UPI_ID_ON_FILE as a structured error', () async {
      final repo = RewardsRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            return _json({'success': false, 'error_code': 'NO_UPI_ID_ON_FILE', 'message': 'Add a UPI ID first.'}, 400);
          }),
        ),
      );
      expect(
        () => repo.redeem(rewardId: 'rwd-1', accessToken: 'tok-1', idempotencyKey: 'k'),
        throwsA(isA<ApiException>().having((e) => e.errorCode, 'errorCode', 'NO_UPI_ID_ON_FILE')),
      );
    });

    test('a FAILED mock payout is surfaced, not thrown — a failed redemption is not an app error', () async {
      final repo = RewardsRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            return _json({
              'txn_id': 'txn-1',
              'home_user_id': 'user-1',
              'reward_id': 'rwd-1',
              'type': 'REDEMPTION',
              'amount': '5.00',
              'status': 'FAILED',
              'created_at': '2026-09-01T00:00:00',
            }, 200);
          }),
        ),
      );
      final txn = await repo.redeem(rewardId: 'rwd-1', accessToken: 'tok-1', idempotencyKey: 'k');
      expect(txn.succeeded, isFalse);
    });
  });

  test('lists user-owned reward transactions with pagination', () async {
    late String path;
    final repo = RewardsRepository(
      apiClient: ApiClient(
        baseUrl: 'http://test',
        client: MockClient((request) async {
          path = request.url.toString();
          return _json({
            'transactions': [
              {
                'txn_id': 'txn-1',
                'home_user_id': 'user-1',
                'reward_id': 'reward-1',
                'type': 'CREDIT',
                'amount': '5.00',
                'status': 'SUCCEEDED',
                'created_at': '2026-09-01T00:00:00',
              },
            ],
            'has_more': true,
          }, 200);
        }),
      ),
    );
    final page = await repo.listMyTransactions(accessToken: 'tok-1', offset: 20);
    expect(page.transactions.single.isCredit, isTrue);
    expect(page.hasMore, isTrue);
    expect(path, contains('/api/v1/rewards/transactions/mine?limit=20&offset=20'));
  });

  test('parses persisted financial summary without using estimates', () async {
    final repo = RewardsRepository(
      apiClient: ApiClient(
        baseUrl: 'http://test',
        client: MockClient((_) async => _json({
          'completed_credits': '10.00',
          'completed_redemptions': '5.00',
          'pending_amount': '0',
          'failed_count': 1,
        }, 200)),
      ),
    );
    final summary = await repo.transactionSummary('tok-1');
    expect(summary.completedCredits, '10.00');
    expect(summary.completedRedemptions, '5.00');
    expect(summary.pendingAmount, '0');
    expect(summary.failedCount, 1);
  });
}
